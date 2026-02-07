import {
  CheckCircleIcon,
  ChevronUp,
  ClipboardListIcon,
  Loader2Icon,
  XCircleIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Streamdown } from "streamdown";

import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtStep,
} from "@/components/ai-elements/chain-of-thought";
import { Shimmer } from "@/components/ai-elements/shimmer";
import { Button } from "@/components/ui/button";
import { ShineBorder } from "@/components/ui/shine-border";
import { useI18n } from "@/core/i18n/hooks";
import { streamdownPlugins } from "@/core/streamdown";
import { useSubtask } from "@/core/tasks/context";
import { cn } from "@/lib/utils";

export function SubtaskCard({
  className,
  taskId,
}: {
  className?: string;
  taskId: string;
  isLoading: boolean;
}) {
  const { t } = useI18n();
  const [collapsed, setCollapsed] = useState(true);
  const task = useSubtask(taskId)!;
  const icon = useMemo(() => {
    if (task.status === "completed") {
      return <CheckCircleIcon className="size-3" />;
    } else if (task.status === "failed") {
      return <XCircleIcon className="size-3 text-red-500" />;
    } else if (task.status === "in_progress") {
      return <Loader2Icon className="size-3 animate-spin" />;
    }
  }, [task.status]);
  return (
    <ChainOfThought
      className={cn("relative w-full gap-2 rounded-lg border py-0", className)}
      open={!collapsed}
    >
      {task.status === "in_progress" && (
        <ShineBorder
          borderWidth={1.5}
          shineColor={["#A07CFE", "#FE8FB5", "#FFBE7B"]}
        />
      )}
      <div className="flex w-full items-center justify-between p-0.5">
        <Button
          className="w-full items-start justify-start text-left"
          variant="ghost"
          onClick={() => setCollapsed(!collapsed)}
        >
          <div className="flex w-full items-center justify-between">
            <ChainOfThoughtStep
              className="font-normal"
              label={
                task.status === "in_progress" ? (
                  <Shimmer duration={3} spread={3}>
                    {task.description}
                  </Shimmer>
                ) : (
                  task.description
                )
              }
              icon={<ClipboardListIcon />}
            ></ChainOfThoughtStep>
            <div className="flex items-center gap-1">
              {collapsed && (
                <div
                  className={cn(
                    "text-muted-foreground flex items-center gap-1 text-xs font-normal",
                    task.status === "failed" ? "text-red-500 opacity-67" : "",
                  )}
                >
                  {icon}
                  {t.subtasks[task.status]}
                </div>
              )}
              <ChevronUp
                className={cn(
                  "text-muted-foreground size-4",
                  !collapsed ? "" : "rotate-180",
                )}
              />
            </div>
          </div>
        </Button>
      </div>
      <ChainOfThoughtContent className="px-4 pb-4">
        {task.prompt && (
          <ChainOfThoughtStep
            label={
              <Streamdown {...streamdownPlugins}>{task.prompt}</Streamdown>
            }
          ></ChainOfThoughtStep>
        )}
        {task.status === "completed" && (
          <>
            <ChainOfThoughtStep
              label={t.subtasks.completed}
              icon={<CheckCircleIcon className="size-4" />}
            ></ChainOfThoughtStep>
            <ChainOfThoughtStep
              label={
                <Streamdown {...streamdownPlugins}>{task.result}</Streamdown>
              }
            ></ChainOfThoughtStep>
          </>
        )}
        {task.status === "failed" && (
          <ChainOfThoughtStep
            label={<div className="text-red-500">{task.error}</div>}
            icon={<XCircleIcon className="size-4 text-red-500" />}
          ></ChainOfThoughtStep>
        )}
      </ChainOfThoughtContent>
    </ChainOfThought>
  );
}
