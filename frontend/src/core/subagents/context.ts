import { createContext, useContext } from "react";

import type { SubagentState } from "../threads/types";

export const SubagentContext = createContext<Map<string, SubagentState>>(new Map());

export function useSubagentContext() {
  const context = useContext(SubagentContext);
  if (context === undefined) {
    throw new Error("useSubagentContext must be used within a SubagentContext.Provider");
  }
  return context;
}