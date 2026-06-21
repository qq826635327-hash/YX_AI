import { TaskCenter } from "@/components/TaskCenter";

/** 全部项目任务视图（跨项目任务总览）。 */
export function TasksAllPage() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b px-4 py-3">
        <h1 className="text-lg font-semibold">全部项目任务</h1>
        <p className="text-xs text-muted-foreground">展示所有项目的生成任务</p>
      </div>
      <div className="flex-1 overflow-hidden">
        <TaskCenter filter="all" />
      </div>
    </div>
  );
}
