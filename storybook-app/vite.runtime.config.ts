import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  build: {
    outDir: "dist-pixoo-runtime",
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, "runtime.html"),
    },
  },
});
