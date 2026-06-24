/** 应用根组件与路由配置。 */

import { Routes, Route, Navigate } from "react-router-dom";
import { MainLayout } from "@/components/layout/MainLayout";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { HomePage } from "@/pages/HomePage";
import { ProjectListPage } from "@/pages/ProjectListPage";
import { ProjectDetailPage } from "@/pages/ProjectDetailPage";
import { ScriptPage } from "@/pages/ScriptPage";
import { CharactersPage } from "@/pages/CharactersPage";
import { ScenesPage } from "@/pages/ScenesPage";
import { PropsPage } from "@/pages/PropsPage";
import { CharacterDetailPage } from "@/pages/CharacterDetailPage";
import { SceneDetailPage } from "@/pages/SceneDetailPage";
import { PropDetailPage } from "@/pages/PropDetailPage";
import { EpisodesPage } from "@/pages/EpisodesPage";
import { TasksPage } from "@/pages/TasksPage";
import { TasksAllPage } from "@/pages/TasksAllPage";
import { SettingsApiPage } from "@/pages/settings/SettingsApiPage";
import { SettingsModelsPage } from "@/pages/settings/SettingsModelsPage";
import { SettingsComfyuiWorkflowsPage } from "@/pages/settings/SettingsComfyuiWorkflowsPage";
import { SettingsPromptsPage } from "@/pages/settings/SettingsPromptsPage";
import { SettingsImageHostingPage } from "@/pages/settings/SettingsImageHostingPage";
import { SystemStatusPage } from "@/pages/SystemStatusPage";

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<MainLayout />}>
          {/* 首页（自动跳转最近项目） */}
          <Route path="/" element={<HomePage />} />

          {/* 项目管理 */}
          <Route path="/projects" element={<ProjectListPage />} />

          {/* 项目内页面 */}
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="/projects/:projectId/script" element={<ScriptPage />} />
          <Route path="/projects/:projectId/characters" element={<CharactersPage />} />
          <Route path="/projects/:projectId/characters/:characterId" element={<CharacterDetailPage />} />
          <Route path="/projects/:projectId/scenes" element={<ScenesPage />} />
          <Route path="/projects/:projectId/scenes/:sceneId" element={<SceneDetailPage />} />
          <Route path="/projects/:projectId/props" element={<PropsPage />} />
          <Route path="/projects/:projectId/props/:propId" element={<PropDetailPage />} />
          <Route path="/projects/:projectId/episodes" element={<EpisodesPage />} />

          {/* 任务中心 */}
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/tasks/all" element={<TasksAllPage />} />

          {/* 配置中心 */}
          <Route path="/settings/api" element={<SettingsApiPage />} />
          <Route path="/settings/image-hosting" element={<SettingsImageHostingPage />} />
          <Route path="/settings/models" element={<SettingsModelsPage />} />
          <Route path="/settings/comfyui-workflows" element={<SettingsComfyuiWorkflowsPage />} />
          <Route path="/settings/prompts" element={<SettingsPromptsPage />} />
          <Route path="/settings/system-status" element={<SystemStatusPage />} />
          {/* 兼容旧路径 */}
          <Route path="/settings" element={<Navigate to="/settings/api" replace />} />

          {/* 兜底 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}
