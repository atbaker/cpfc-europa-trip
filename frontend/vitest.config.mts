import { defineConfig } from "vitest/config";
export default defineConfig({ test: { include: ["lib/**/*.test.ts", "components/**/*.test.tsx"], environment: "jsdom", globals: true, setupFiles: ["./test/setup.ts"] } });
