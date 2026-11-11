// The editor runs the gcdiagram Python package in Pyodide. This plugin serves, and for
// builds copies, two things that are not part of the JavaScript bundle:
//
//   /pyodide/...               the Pyodide runtime from node_modules (no CDN: works offline)
//   /gcdiagram-sources.json    the live Python package (src/gcdiagram) as {path: text}
//
// Editing a .py file under src/gcdiagram reloads the page with the new code.

import { readFileSync, readdirSync, statSync } from "node:fs";
import type { ServerResponse } from "node:http";
import { dirname, extname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { type Plugin, defineConfig } from "vite";

const here = dirname(fileURLToPath(import.meta.url));
const packageDir = join(here, "..", "src", "gcdiagram");
const pyodideDir = join(here, "node_modules", "pyodide");
const PYODIDE_FILES = [
  "pyodide.mjs",
  "pyodide.asm.mjs",
  "pyodide.asm.wasm",
  "python_stdlib.zip",
  "pyodide-lock.json",
];
const MIME: Record<string, string> = {
  ".mjs": "text/javascript",
  ".wasm": "application/wasm",
  ".zip": "application/zip",
  ".json": "application/json",
};

/** The Python package as {"gcdiagram/<path>": text}, for writing into Pyodide's file system. */
function pythonSources(): string {
  const files: Record<string, string> = {};
  const walk = (dir: string) => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) {
        if (name !== "__pycache__") walk(path);
      } else if (name.endsWith(".py") || name.endsWith(".json")) {
        const rel = relative(join(packageDir, ".."), path).split(sep).join("/");
        files[rel] = readFileSync(path, "utf8");
      }
    }
  };
  walk(packageDir);
  return JSON.stringify(files);
}

function send(res: ServerResponse, type: string, body: string | Buffer): void {
  res.setHeader("Content-Type", type);
  res.setHeader("Cache-Control", "no-cache");
  res.end(body);
}

function gcdiagramPython(): Plugin {
  return {
    name: "gcdiagram-python",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const path = (req.url ?? "").split("?")[0]!;
        if (path === "/gcdiagram-sources.json") return send(res, MIME[".json"]!, pythonSources());
        const file = path.startsWith("/pyodide/") ? path.slice("/pyodide/".length) : "";
        if (PYODIDE_FILES.includes(file)) {
          return send(res, MIME[extname(file)]!, readFileSync(join(pyodideDir, file)));
        }
        next();
      });
      server.watcher.add(packageDir);
      server.watcher.on("change", (file) => {
        if (file.startsWith(packageDir) && file.endsWith(".py")) server.ws.send({ type: "full-reload" });
      });
    },
    generateBundle() {
      this.emitFile({ type: "asset", fileName: "gcdiagram-sources.json", source: pythonSources() });
      for (const file of PYODIDE_FILES) {
        this.emitFile({ type: "asset", fileName: `pyodide/${file}`, source: readFileSync(join(pyodideDir, file)) });
      }
    },
  };
}

export default defineConfig({
  plugins: [gcdiagramPython()],
  worker: { format: "es" },
  server: { port: 5173, strictPort: true },
  preview: { port: 4173, strictPort: true },
});
