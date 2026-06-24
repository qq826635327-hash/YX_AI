/** 主布局：顶部栏 + 左侧边栏 + 内容区 + 右侧属性面板 + Toast + 日志查看器。 */

import { Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { TopBar } from "./TopBar";
import { Sidebar } from "./Sidebar";
import { RightPanel } from "./RightPanel";
import { ToastContainer } from "./ToastContainer";
import { LogViewer } from "@/components/LogViewer";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useTaskWsSubscription, useScriptWsSubscription } from "@/hooks/useWs";
import { useLogWsSubscription } from "@/hooks/useLogWsSubscription";
import { useUiStore } from "@/stores/ui";

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
  const location = useLocation();
  const setSelectedEntity = useUiStore((s) => s.setSelectedEntity);

  // 离开实体详情页时清空右侧属性面板（仅清空实体类型，保留 asset/shot_frame）
  useEffect(() => {
    const isEntityDetail = /^\/projects\/[^/]+\/(characters|scenes|props)\/[^/]+$/.test(location.pathname);
    const current = useUiStore.getState().selectedEntity;
    if (!isEntityDetail && current && (current.type === "character" || current.type === "scene" || current.type === "prop")) {
      setSelectedEntity(null);
    }
  }, [location.pathname, setSelectedEntity]);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      {/* 顶部栏 */}
      <TopBar />

      {/* 主体：左侧边栏 + 内容区 + 右侧属性面板 */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto bg-background">
          {/* WS 订阅：任务进度推送 + 剧本解析状态推送 + 日志订阅 */}
          <WsSubscriptions />
          <Outlet />
        </main>
        <RightPanel />
      </div>

      <ToastContainer />
      {/* 浮动日志查看器（右下角） */}
      <LogViewer />
      {/* 全局异步确认对话框（替代原生 confirm） */}
      <ConfirmDialog />
    </div>
  );
}
