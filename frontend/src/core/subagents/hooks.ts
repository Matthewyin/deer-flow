import { useCallback, useEffect, useRef, useState } from "react";

import type { SubagentProgressEvent, SubagentState } from "../threads/types";

export function useSubagentStates() {
  const [subagents, setSubagents] = useState<Map<string, SubagentState>>(new Map());
  const subagentsRef = useRef<Map<string, SubagentState>>(new Map());

  // 保持 ref 与 state 同步
  useEffect(() => {
    subagentsRef.current = subagents;
  }, [subagents]);

  const handleSubagentProgress = useCallback((event: SubagentProgressEvent) => {
    console.log('[SubagentProgress] Received event:', event);

    const { task_id, trace_id, subagent_type, event_type, result, error } = event;

    setSubagents(prev => {
      const newSubagents = new Map(prev);
      const existingState = newSubagents.get(task_id) || {
        task_id,
        trace_id,
        subagent_type,
        status: "running" as const,
      };

      let newState = { ...existingState };

      switch (event_type) {
        case "started":
          newState = {
            ...newState,
            status: "running",
          };
          break;

        case "completed":
          newState = {
            ...newState,
            status: "completed",
            result,
          };
          break;

        case "failed":
          newState = {
            ...newState,
            status: "failed",
            error,
          };
          break;
      }

      newSubagents.set(task_id, newState);
      return newSubagents;
    });
  }, []);

  const clearSubagents = useCallback(() => {
    setSubagents(new Map());
  }, []);

  return {
    subagents,
    handleSubagentProgress,
    clearSubagents,
  };
}