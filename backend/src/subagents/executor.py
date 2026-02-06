"""Subagent execution engine."""

import logging
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from langchain.agents import create_agent
from langchain.tools import BaseTool
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from src.agents.thread_state import SandboxState, ThreadDataState, ThreadState
from src.models import create_chat_model
from src.subagents.config import SubagentConfig

logger = logging.getLogger(__name__)


class SubagentStatus(Enum):
    """Status of a subagent execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SubagentResult:
    """Result of a subagent execution.

    Attributes:
        task_id: Unique identifier for this execution.
        trace_id: Trace ID for distributed tracing (links parent and subagent logs).
        status: Current status of the execution.
        result: The final result message (if completed).
        error: Error message (if failed).
        started_at: When execution started.
        completed_at: When execution completed.
    """

    task_id: str
    trace_id: str
    status: SubagentStatus
    result: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


# Global storage for background task results
_background_tasks: dict[str, SubagentResult] = {}
_background_tasks_lock = threading.Lock()

# Thread pool for background task scheduling and orchestration
_scheduler_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="subagent-scheduler-")

# Thread pool for actual subagent execution (with timeout support)
# Larger pool to avoid blocking when scheduler submits execution tasks
_execution_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="subagent-exec-")


def _filter_tools(
    all_tools: list[BaseTool],
    allowed: list[str] | None,
    disallowed: list[str] | None,
) -> list[BaseTool]:
    """Filter tools based on subagent configuration.

    Args:
        all_tools: List of all available tools.
        allowed: Optional allowlist of tool names. If provided, only these tools are included.
        disallowed: Optional denylist of tool names. These tools are always excluded.

    Returns:
        Filtered list of tools.
    """
    filtered = all_tools

    # Apply allowlist if specified
    if allowed is not None:
        allowed_set = set(allowed)
        filtered = [t for t in filtered if t.name in allowed_set]

    # Apply denylist
    if disallowed is not None:
        disallowed_set = set(disallowed)
        filtered = [t for t in filtered if t.name not in disallowed_set]

    return filtered


def _get_model_name(config: SubagentConfig, parent_model: str | None) -> str | None:
    """Resolve the model name for a subagent.

    Args:
        config: Subagent configuration.
        parent_model: The parent agent's model name.

    Returns:
        Model name to use, or None to use default.
    """
    if config.model == "inherit":
        return parent_model
    return config.model


class SubagentExecutor:
    """Executor for running subagents."""

    def __init__(
        self,
        config: SubagentConfig,
        tools: list[BaseTool],
        parent_model: str | None = None,
        sandbox_state: SandboxState | None = None,
        thread_data: ThreadDataState | None = None,
        thread_id: str | None = None,
        trace_id: str | None = None,
    ):
        """Initialize the executor.

        Args:
            config: Subagent configuration.
            tools: List of all available tools (will be filtered).
            parent_model: The parent agent's model name for inheritance.
            sandbox_state: Sandbox state from parent agent.
            thread_data: Thread data from parent agent.
            thread_id: Thread ID for sandbox operations.
            trace_id: Trace ID from parent for distributed tracing.
        """
        self.config = config
        self.parent_model = parent_model
        self.sandbox_state = sandbox_state
        self.thread_data = thread_data
        self.thread_id = thread_id
        # Generate trace_id if not provided (for top-level calls)
        self.trace_id = trace_id or str(uuid.uuid4())[:8]

        # Filter tools based on config
        self.tools = _filter_tools(
            tools,
            config.tools,
            config.disallowed_tools,
        )

        logger.info(f"[trace={self.trace_id}] SubagentExecutor initialized: {config.name} with {len(self.tools)} tools")

    def _create_agent(self):
        """Create the agent instance."""
        model_name = _get_model_name(self.config, self.parent_model)
        model = create_chat_model(name=model_name, thinking_enabled=False)

        # Create a simple agent without middlewares
        # Subagents don't need the full middleware chain
        return create_agent(
            model=model,
            tools=self.tools,
            system_prompt=self.config.system_prompt,
            state_schema=ThreadState,
        )

    def _build_initial_state(self, task: str) -> dict[str, Any]:
        """Build the initial state for agent execution.

        Args:
            task: The task description.

        Returns:
            Initial state dictionary.
        """
        state: dict[str, Any] = {
            "messages": [HumanMessage(content=task)],
        }

        # Pass through sandbox and thread data from parent
        if self.sandbox_state is not None:
            state["sandbox"] = self.sandbox_state
        if self.thread_data is not None:
            state["thread_data"] = self.thread_data

        return state

    def execute(self, task: str) -> SubagentResult:
        """Execute a task synchronously.

        Args:
            task: The task description for the subagent.

        Returns:
            SubagentResult with the execution result.
        """
        task_id = str(uuid.uuid4())[:8]
        result = SubagentResult(
            task_id=task_id,
            trace_id=self.trace_id,
            status=SubagentStatus.RUNNING,
            started_at=datetime.now(),
        )

        try:
            agent = self._create_agent()
            state = self._build_initial_state(task)

            # Build config with thread_id for sandbox access and recursion limit
            run_config: RunnableConfig = {
                "recursion_limit": self.config.max_turns,
            }
            if self.thread_id:
                run_config["configurable"] = {"thread_id": self.thread_id}

            logger.info(f"[trace={self.trace_id}] Subagent {self.config.name} starting execution with max_turns={self.config.max_turns}")

            # Run the agent using invoke for complete result
            # Note: invoke() runs until completion or interruption
            # Timeout is handled at the execute_async level, not here
            final_state = agent.invoke(state, config=run_config)  # type: ignore[arg-type]

            logger.info(f"[trace={self.trace_id}] Subagent {self.config.name} completed execution")

            # Extract the final message - find the last AIMessage
            messages = final_state.get("messages", [])
            logger.info(f"[trace={self.trace_id}] Subagent {self.config.name} final messages count: {len(messages)}")

            # Find the last AIMessage in the conversation
            last_ai_message = None
            for msg in reversed(messages):
                if isinstance(msg, AIMessage):
                    last_ai_message = msg
                    break

            if last_ai_message is not None:
                content = last_ai_message.content
                logger.info(f"[trace={self.trace_id}] Subagent {self.config.name} last AI message content type: {type(content)}")

                # Handle both str and list content types
                if isinstance(content, str):
                    result.result = content
                elif isinstance(content, list):
                    # Extract text from list of content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, str):
                            text_parts.append(block)
                        elif isinstance(block, dict) and "text" in block:
                            text_parts.append(block["text"])
                    result.result = "\n".join(text_parts) if text_parts else "No text content in response"
                else:
                    result.result = str(content)
            elif messages:
                # Fallback: use the last message if no AIMessage found
                last_message = messages[-1]
                logger.warning(f"[trace={self.trace_id}] Subagent {self.config.name} no AIMessage found, using last message: {type(last_message)}")
                result.result = str(last_message.content) if hasattr(last_message, "content") else str(last_message)
            else:
                logger.warning(f"[trace={self.trace_id}] Subagent {self.config.name} no messages in final state")
                result.result = "No response generated"

            result.status = SubagentStatus.COMPLETED
            result.completed_at = datetime.now()

        except Exception as e:
            logger.exception(f"[trace={self.trace_id}] Subagent {self.config.name} execution failed")
            result.status = SubagentStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now()

        return result

    def execute_async(self, task: str) -> str:
        """Start a task execution in the background.

        Args:
            task: The task description for the subagent.

        Returns:
            Task ID that can be used to check status later.
        """
        task_id = str(uuid.uuid4())[:8]

        # Create initial pending result
        result = SubagentResult(
            task_id=task_id,
            trace_id=self.trace_id,
            status=SubagentStatus.PENDING,
        )

        logger.info(f"[trace={self.trace_id}] Subagent {self.config.name} starting async execution, task_id={task_id}")

        with _background_tasks_lock:
            _background_tasks[task_id] = result

        # Submit to scheduler pool
        def run_task():
            with _background_tasks_lock:
                _background_tasks[task_id].status = SubagentStatus.RUNNING
                _background_tasks[task_id].started_at = datetime.now()

            try:
                # Submit execution to execution pool with timeout
                execution_future: Future = _execution_pool.submit(self.execute, task)
                try:
                    # Wait for execution with timeout
                    exec_result = execution_future.result(timeout=self.config.timeout_seconds)
                    with _background_tasks_lock:
                        _background_tasks[task_id].status = exec_result.status
                        _background_tasks[task_id].result = exec_result.result
                        _background_tasks[task_id].error = exec_result.error
                        _background_tasks[task_id].completed_at = datetime.now()
                except FuturesTimeoutError:
                    logger.error(
                        f"[trace={self.trace_id}] Subagent {self.config.name} execution timed out after {self.config.timeout_seconds}s"
                    )
                    with _background_tasks_lock:
                        _background_tasks[task_id].status = SubagentStatus.FAILED
                        _background_tasks[task_id].error = f"Execution timed out after {self.config.timeout_seconds} seconds"
                        _background_tasks[task_id].completed_at = datetime.now()
                    # Cancel the future (best effort - may not stop the actual execution)
                    execution_future.cancel()
            except Exception as e:
                logger.exception(f"[trace={self.trace_id}] Subagent {self.config.name} async execution failed")
                with _background_tasks_lock:
                    _background_tasks[task_id].status = SubagentStatus.FAILED
                    _background_tasks[task_id].error = str(e)
                    _background_tasks[task_id].completed_at = datetime.now()

        _scheduler_pool.submit(run_task)
        return task_id


def get_background_task_result(task_id: str) -> SubagentResult | None:
    """Get the result of a background task.

    Args:
        task_id: The task ID returned by execute_async.

    Returns:
        SubagentResult if found, None otherwise.
    """
    with _background_tasks_lock:
        return _background_tasks.get(task_id)


def list_background_tasks() -> list[SubagentResult]:
    """List all background tasks.

    Returns:
        List of all SubagentResult instances.
    """
    with _background_tasks_lock:
        return list(_background_tasks.values())
