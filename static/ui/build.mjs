import { transform } from "esbuild";
import { readFile, writeFile, mkdir, stat, watch } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const distDir = join(here, "dist");
const bundlePath = join(distDir, "bundle.js");

const files = [
  "shared.jsx",
  "screens.jsx",
  "console.jsx",
  "flow-icons.jsx",
  "flow-data.jsx",
  "flow-history.jsx",
  "flow-library.jsx",
  "flow-templates.jsx",
  "flow-codeeditor.jsx",
  "flow-canvas.jsx",
  "flow-inspector.jsx",
  "flow-app.jsx",
  "prototype-v2.jsx",
];

async function build() {
  const chunks = [];
  for (const name of files) {
    const src = await readFile(join(here, name), "utf8");
    chunks.push(`// ===== ${name} =====\n${src}\n`);
  }
  const combined = chunks.join("\n");

  const result = await transform(combined, {
    loader: "jsx",
    jsx: "transform",
    target: "es2018",
    sourcemap: "inline",
    legalComments: "none",
  });

  await mkdir(distDir, { recursive: true });
  await writeFile(bundlePath, result.code);
  const ts = new Date().toISOString().slice(11, 19);
  console.log(`[${ts}] built dist/bundle.js (${result.code.length.toLocaleString()} bytes)`);
}

async function isStale() {
  if (!existsSync(bundlePath)) return true;
  const bundleStat = await stat(bundlePath);
  for (const name of files) {
    const s = await stat(join(here, name));
    if (s.mtimeMs > bundleStat.mtimeMs) return name;
  }
  return false;
}

const args = process.argv.slice(2);
if (args.includes("--check")) {
  const stale = await isStale();
  if (stale) {
    console.error(`Bundle is stale — ${stale === true ? "missing" : `${stale} is newer`}. Run: npm run build:ui`);
    process.exit(1);
  }
  console.log("Bundle is up to date.");
  process.exit(0);
}

await build();

if (args.includes("--watch")) {
  console.log("Watching for .jsx changes…");
  (async () => {
    try {
      for await (const evt of watch(here, { recursive: false })) {
        if (evt.filename && evt.filename.endsWith(".jsx")) {
          try { await build(); } catch (err) { console.error("build failed:", err.message); }
        }
      }
    } catch (err) {
      console.error("watcher stopped:", err.message);
    }
  })();
} else {
  const stale = await isStale();
  if (stale && stale !== true) {
    console.warn(`Warning: ${stale} mtime is newer than bundle (just-built — should not happen). Investigate.`);
  }
}
