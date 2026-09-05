import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: "0.0.0.0",
    strictPort: true,
    // Requests reach the container as either "localhost" or "127.0.0.1"
    // depending on how Docker Desktop's port-forwarding resolves on the
    // host, so both must be explicitly trusted (Vite validates the Host
    // header against this list once `host` is set to a non-default value).
    allowedHosts: ["localhost", "127.0.0.1"],
    watch: {
      // Files are edited on the Windows host and reach this container via a
      // WSL2 bind mount — inotify events from host-side edits don't reliably
      // propagate across that boundary, so Vite's default watcher can miss
      // changes entirely (confirmed: edited App.tsx on disk, Vite kept
      // serving the pre-edit content indefinitely). Polling works regardless.
      usePolling: true,
      interval: 300,
    },
  },
});
