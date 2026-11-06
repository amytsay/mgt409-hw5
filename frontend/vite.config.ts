import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dashboard runs on http://localhost:5173 (the origin the backend's CORS allows).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
});
