import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// Vite 配置
// 开发服务器代理配置：
// - 默认指向 127.0.0.1:8000（与后端默认端口一致）
// - 局域网访问：可以通过环境变量 VITE_API_TARGET 和 VITE_WS_TARGET 覆盖
//   例如：VITE_API_TARGET=http://192.168.1.100:8000 npm run dev
const apiTarget = process.env.VITE_API_TARGET || "http://127.0.0.1:8000";
const wsTarget = process.env.VITE_WS_TARGET || "ws://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    strictPort: true, // 端口被占用时报错而非自动换端口
    // 允许局域网访问（--host 参数也能开启）
    host: process.env.VITE_HOST || "127.0.0.1",
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
      "/ws": {
        target: wsTarget,
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
