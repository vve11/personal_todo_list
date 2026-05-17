import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Bind IPv4 loopback so http://127.0.0.1:5173 works (default can be IPv6-only [::1]).
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        // Must match the Python server port (default 5050; avoid 5000 on Windows if something else is bound there).
        target: `http://127.0.0.1:${process.env.VITE_API_PORT || "5050"}`,
        changeOrigin: true,
      },
    },
  },
});
