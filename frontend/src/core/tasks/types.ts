export interface Subtask {
  id: string;
  status: "in_progress" | "completed" | "failed";
  subagent_type: string;
  description: string;
  prompt: string;
  result?: string;
  error?: string;
}
