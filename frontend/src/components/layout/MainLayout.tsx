/** 主布局：顶部栏 + 侧边栏 + 内容区 + Toast + 日志查看器。 */

import { Outlet, useLocation } from "react-router-dom";
import { TopBar } from "./TopBar";
import { Sidebar } from "./Sidebar";
import { ToastContainer } from "./ToastContainer";
import { LogViewer } from "@/components/LogViewer";
import { useTaskWsSubscription, useScriptWsSubscription } from "@/hooks/useWs";
import { useLogWsSubscription } from "@/hooks/useLogWsSubscription";

/**
 * WS 订阅挂载点：在整个主布局内激活任务状态推送。
 * 剧本解析状态订阅依赖当前 projectId（可选）。
 */
function WsSubscriptions() {
  // 从 React Router 获取 pathname，确保客户端导航时 projectId 同步更新
  const location = useLocation();
  const match = location.pathname.match(/^\/projects\/([^/]+)/);
  const projectId = match ? match[1] : undefined;
  useTaskWsSubscription();
  useScriptWsSubscription(projectId);
  useLogWsSubscription();
  return null;
}

export function MainLayout() {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      {/* 顶部栏 */}
      <TopBar />

      {/* 主体：左侧边栏 + 内容区 */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          {/* WS 订阅：任务进度推送 + 剧本解析状态推送 + 日志订阅 */}
          <WsSubscriptions />
          <Outlet />
        </main>
      </div>

      <ToastContainer />
      {/* 浮动日志查看器（右下角） */}
      <LogViewer />
    </div>
  );
}
