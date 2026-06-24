import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";
import { initTheme } from "@/stores/ui";
import { tasksWs, scriptWs, logsWs } from "@/api/websocket";
import { logger as log } from "@/stores/logStore";
import { perf } from "@/perf";

// 初始化主题
initTheme();

// 安装全局前端错误捕获（把浏览器/React 错误也写到 logStore）
function installGlobalErrorHandlers() {
  // 1. JS 运行时错误
  window.addEventListener("error", (event) => {
    try {
      perf.mark("error.js", {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
      });
      log.error(
        event.message || "Uncaught error",
        "frontend",
        event.filename ? `${event.filename}:${event.lineno}` : "window.error",
        {
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno,
          stack: event.error?.stack,
        }
      );
    } catch {
      /* 忽略日志失败 */
    }
  });

  // 2. Promise 拒绝未捕获
  window.addEventListener("unhandledrejection", (event) => {
    try {
      perf.mark("error.promise", { reason: String(event.reason) });
      const reason = event.reason;
      const message =
        reason instanceof Error ? `${reason.name}: ${reason.message}` : String(reason);
      log.error(
        `Unhandled rejection: ${message}`,
        "frontend",
        "promise",
        { stack: reason instanceof Error ? reason.stack : undefined }
      );
    } catch {
      /* 忽略日志失败 */
    }
  });

  // 3. 拦截 console.error（部分第三方库通过 console.error 报错）
  const originalConsoleError = console.error.bind(console);
  let _isLogging = false; // 防止重入（log.error 内部若触发 console.error 会无限递归）
  console.error = (...args: unknown[]) => {
    if (_isLogging) {
      originalConsoleError(...args);
      return;
    }
    try {
      _isLogging = true;
      const text = args
        .map((a) => (typeof a === "string" ? a : a instanceof Error ? a.stack : JSON.stringify(a)))
        .join(" ");
      // 过滤掉一些噪音（React DevTools 提示、HMR、IDE/Electron 内部错误、导航中断请求）
      if (
        text.includes("Download the React DevTools") ||
        text.includes("[HMR]") ||
        text.includes("getThemeColors") ||
        text.includes("preload script") ||
        text.includes("net::ERR_ABORTED") ||
        text.length < 3
      ) {
        originalConsoleError(...args);
        return;
      }
      log.error(text, "frontend", "console.error");
    } catch {
      /* 忽略 */
    } finally {
      _isLogging = false;
    }
    originalConsoleError(...args);
  };
}

installGlobalErrorHandlers();

// 连接 WebSocket
tasksWs.connect();
scriptWs.connect();
logsWs.connect();
// 页面关闭前主动断开 WebSocket，减少后端异常残留连接
window.addEventListener("beforeunload", () => {
  try {
    tasksWs.close();
    scriptWs.close();
    logsWs.close();
  } catch {
    /* 忽略 */
  }
});

// 启动性能监控
perf.start();

// 性能告警不再弹 Toast，只在 PerfMonitor 面板中展示

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,       // 10 秒内视为新鲜，避免每次 mount 都重新请求
      retry: 1,
      refetchOnWindowFocus: false,
      refetchOnMount: true,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
