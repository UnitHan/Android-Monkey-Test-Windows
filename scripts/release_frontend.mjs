// Tauri reads its version before the build hook; increment it in the release wrapper first.
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

const version = JSON.parse(readFileSync(new URL("../frontend/package.json", import.meta.url))).version;
if (process.env.MONKEY_RELEASE_BUILD !== version) {
  console.error("설치 패키지는 npm run installer로 빌드하세요. 버전 증가와 런타임 포함이 필요합니다.");
  process.exit(1);
}
const result = spawnSync(process.execPath, ["node_modules/typescript/bin/tsc", "-b"], { stdio: "inherit" });
if (result.status !== 0) process.exit(result.status ?? 1);
const built = spawnSync(process.execPath, ["node_modules/vite/bin/vite.js", "build"], { stdio: "inherit" });
process.exit(built.status ?? 1);
