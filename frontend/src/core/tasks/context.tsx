import { createContext, useCallback, useContext, useState } from "react";

import type { Subtask } from "./types";

export interface SubtaskContextValue {
  tasks: Map<string, Subtask>;
}

export const SubtaskContext = createContext<SubtaskContextValue>({
  tasks: new Map(),
});

export function SubtasksProvider({ children }: { children: React.ReactNode }) {
  const [tasks] = useState<Map<string, Subtask>>(new Map());
  return (
    <SubtaskContext.Provider value={{ tasks }}>
      {children}
    </SubtaskContext.Provider>
  );
}

export function useSubtaskContext() {
  const context = useContext(SubtaskContext);
  if (context === undefined) {
    throw new Error(
      "useSubtaskContext must be used within a SubtaskContext.Provider",
    );
  }
  return context;
}

export function useSubtask(id: string) {
  const { tasks } = useSubtaskContext();
  return tasks.get(id);
}

export function useUpdateSubtask() {
  const { tasks } = useSubtaskContext();
  const updateSubtask = useCallback(
    (task: Partial<Subtask> & { id: string }) => {
      tasks.set(task.id, { ...tasks.get(task.id), ...task } as Subtask);
    },
    [tasks],
  );
  return updateSubtask;
}
