import { defineConfig } from "vitest/config"
import path from "node:path"

export default defineConfig({
  test: {
    environment: "node",
    // Include src/app (route handlers, pages) and .tsx, not only src/**.ts, so
    // tests colocated with components are discovered. The environment is node;
    // a component test touching the DOM would have to pin jsdom in its own
    // file.
    include: ["{src,app}/**/*.test.{ts,tsx}"],
  },
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "src") },
  },
})
