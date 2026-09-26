import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Backend runs on 8002 (8001 is taken by oMLX)
    proxy: { "/api": "http://localhost:8002" },
  },
});
