// ESLint for the frontend workspace: the recommended JavaScript rules, typescript-eslint's strict rules and the
// React hooks rules. CI runs it with no warnings allowed (npm run lint).
import js from "@eslint/js";
import { defineConfig, globalIgnores } from "eslint/config";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default defineConfig(
  globalIgnores(["**/dist/", "**/node_modules/"]),
  js.configs.recommended,
  tseslint.configs.strict,
  reactHooks.configs.flat.recommended,
  {
    files: ["apps/*/src/**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
  },
);
