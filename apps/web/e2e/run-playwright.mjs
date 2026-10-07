import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const result = spawnSync(process.execPath,
  [fileURLToPath(new URL("../node_modules/playwright/cli.js", import.meta.url)), ...process.argv.slice(2)],
  { stdio: "inherit", env: { ...process.env,
    PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH ??
      fileURLToPath(new URL("../node_modules/.cache/ms-playwright", import.meta.url)) } });
if (result.error) throw result.error;
process.exit(result.status ?? 1);
