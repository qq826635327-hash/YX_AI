import { useSearchParams } from "react-router-dom";
import { TaskCenter, type TaskFilter } from "@/components/TaskCenter";

const VALID_FILTERS: TaskFilter[] = ["all", "active", "completed", "failed", "cancelled"];

/** 任务中心 - 通过 URL ?filter= 参数切换视图。 */
export function TasksPage() {
  const [searchParams] = useSearchParams();
  const raw = searchParams.get("filter") || "all";
  const filter = VALID_FILTERS.includes(raw as TaskFilter) ? (raw as TaskFilter) : "all";

  return <TaskCenter filter={filter} />;
}
