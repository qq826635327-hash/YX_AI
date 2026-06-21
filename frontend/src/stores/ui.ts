/** 全局 UI 状态管理（Zustand）。 */

import { create } from "zustand";

type ActiveModule = "project" | "tasks" | "config";

interface UiState {
  /** 当前激活的模块（控制左侧菜单显示内容） */
  activeModule: ActiveModule;
  setActiveModule: (m: ActiveModule) => void;

  /** 侧边栏折叠 */
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;

  /** 主题：light / dark / system */
  theme: "light" | "dark" | "system";
  setTheme: (theme: "light" | "dark" | "system") => void;

  /** Toast 通知 */
  toasts: Toast[];
  pushToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}

export interface Toast {
  id: string;
  title?: string;
  description?: string;
  variant: "default" | "success" | "error" | "warning";
  duration?: number;
}

export const useUiStore = create<UiState>((set) => ({
  activeModule: "project",
  setActiveModule: (m) => set({ activeModule: m }),

  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  theme: (localStorage.getItem("theme") as "light" | "dark" | "system") || "system",
  setTheme: (theme) => {
    localStorage.setItem("theme", theme);
    set({ theme });
    applyTheme(theme);
  },

  toasts: [],
  pushToast: (toast) =>
    set((s) => {
      const id = Math.random().toString(36).slice(2);
      const newToast: Toast = { ...toast, id, duration: toast.duration ?? 3000, variant: toast.variant ?? "default" };
      // 自动移除
      if (newToast.duration) {
        setTimeout(() => {
          set((st) => ({ toasts: st.toasts.filter((t) => t.id !== id) }));
        }, newToast.duration);
      }
      return { toasts: [...s.toasts, newToast] };
    }),
  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

/** 应用主题到 <html>。 */
export function applyTheme(theme: "light" | "dark" | "system"): void {
  const root = document.documentElement;
  const isDark =
    theme === "dark" ||
    (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  root.classList.toggle("dark", isDark);
}

/** 初始化主题（在 main.tsx 调用）。 */
export function initTheme(): void {
  const theme = (localStorage.getItem("theme") as "light" | "dark" | "system") || "system";
  applyTheme(theme);
  // 监听系统主题变化
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    const current = (localStorage.getItem("theme") as "light" | "dark" | "system") || "system";
    if (current === "system") applyTheme("system");
  });
}

/** 便捷 toast 方法。 */
export const toast = {
  success: (description: string, title?: string) =>
    useUiStore.getState().pushToast({ title, description, variant: "success" }),
  error: (description: string, title?: string) =>
    useUiStore.getState().pushToast({ title, description, variant: "error" }),
  warning: (description: string, title?: string) =>
    useUiStore.getState().pushToast({ title, description, variant: "warning" }),
  info: (description: string, title?: string) =>
    useUiStore.getState().pushToast({ title, description, variant: "default" }),
};
