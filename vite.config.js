import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendProxy = {
  "/api": {
    target: "http://127.0.0.1:8765",
    changeOrigin: true,
    xfwd: true,
  },
  "/ws": {
    target: "ws://127.0.0.1:8765",
    changeOrigin: true,
    ws: true,
    xfwd: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: backendProxy,
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
    proxy: backendProxy,
  },
});
