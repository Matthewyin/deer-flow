"""Task tool for delegating work to subagents."""

import logging
import time
import uuid
from typing import Literal

from langchain.tools import ToolRuntime, tool
from langgraph.typing import ContextT

from src.agents.thread_state import ThreadState
from src.subagents import SubagentExecutor, get_subagent_config
from src.subagents.executor import SubagentStatus, get_background_task_result

logger = logging.getLogger(__name__)


@tool("task", parse_docstring=True)
def task_tool(
    runtime: ToolRuntime[ContextT, ThreadState],
    subagent_type: Literal["general-purpose", "bash"],
    prompt: str,
    description: str,
    max_turns: int | None = None,
) -> str:
    """Delegate a task to a specialized subagent that runs in its own context.

    Subagents help you:
    - Preserve context by keeping exploration and implementation separate
    - Handle complex multi-step tasks autonomously
    - Execute commands or operations in isolated contexts

    Available subagent types:
    - **general-purpose**: A capable agent for complex, multi-step tasks that require
      both exploration and action. Use when the task requires complex reasoning,
      multiple dependent steps, or would benefit from isolated context.
    - **bash**: Command execution specialist for running bash commands. Use for
      git operations, build processes, or when command output would be verbose.

    When to use this tool:
    - Complex tasks requiring multiple steps or tools
    - Tasks that produce verbose output
    - When you want to isolate context from the main conversation
    - Parallel research or exploration tasks

    When NOT to use this tool:
    - Simple, single-step operations (use tools directly)
    - Tasks requiring user interaction or clarification

    Args:
        subagent_type: The type of subagent to use.
        prompt: The task description for the subagent. Be specific and clear about what needs to be done.
        description: A short (3-5 word) description of the task for logging/display.
        max_turns: Optional maximum number of agent turns. Defaults to subagent's configured max.
    """
    # Get subagent configuration
    config = get_subagent_config(subagent_type)
    if config is None:
        return f"Error: Unknown subagent type '{subagent_type}'. Available: general-purpose, bash"

    # Override max_turns if specified
    if max_turns is not None:
        # Create a copy with updated max_turns
        from dataclasses import replace

        config = replace(config, max_turns=max_turns)

    # Extract parent context from runtime
    sandbox_state = None
    thread_data = None
    thread_id = None
    parent_model = None
    trace_id = None

    if runtime is not None:
        sandbox_state = runtime.state.get("sandbox")
        thread_data = runtime.state.get("thread_data")
        thread_id = runtime.context.get("thread_id")

        # Try to get parent model from configurable
        metadata = runtime.config.get("metadata", {})
        parent_model = metadata.get("model_name")

        # Get or generate trace_id for distributed tracing
        trace_id = metadata.get("trace_id") or str(uuid.uuid4())[:8]

    # Get available tools (excluding task tool to prevent nesting)
    # Lazy import to avoid circular dependency
    from src.tools import get_available_tools

    # Subagents should not have subagent tools enabled (prevent recursive nesting)
    tools = get_available_tools(model_name=parent_model, subagent_enabled=False)

    # Create executor
    executor = SubagentExecutor(
        config=config,
        tools=tools,
        parent_model=parent_model,
        sandbox_state=sandbox_state,
        thread_data=thread_data,
        thread_id=thread_id,
        trace_id=trace_id,
    )

    # Start background execution (always async to prevent blocking)
    task_id = executor.execute_async(prompt)
    logger.info(f"[trace={trace_id}] Started background task {task_id}, polling for completion...")

    # Poll for task completion in backend (removes need for LLM to poll)
    poll_count = 0
    last_status = None

    while True:
        result = get_background_task_result(task_id)

        if result is None:
            logger.error(f"[trace={trace_id}] Task {task_id} not found in background tasks")
            return f"Error: Task {task_id} disappeared from background tasks"

        # Log status changes for debugging
        if result.status != last_status:
            logger.info(f"[trace={trace_id}] Task {task_id} status: {result.status.value}")
            last_status = result.status

        # Check if task completed or failed
        if result.status == SubagentStatus.COMPLETED:
            logger.info(f"[trace={trace_id}] Task {task_id} completed after {poll_count} polls")
            return f"Task Succeeded. Result: {result.result}"
        elif result.status == SubagentStatus.FAILED:
            logger.error(f"[trace={trace_id}] Task {task_id} failed: {result.error}")
            return f"Task failed. Error: {result.error}"

        # Still running, wait before next poll
        time.sleep(10)  # Poll every 10 seconds
        poll_count += 1

        # Optional: Add timeout protection (e.g., max 5 minutes)
        if poll_count > 30:  # 30 * 10s = 5 minutes
            logger.warning(f"[trace={trace_id}] Task {task_id} timed out after {poll_count} polls")
            return f"Task timed out after 5 minutes. Status: {result.status.value}"
