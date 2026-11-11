/// <reference lib="webworker" />
// Runs Pyodide and the gcdiagram package off the main thread. Messages are
// {id, fn, args} -> {id, result} | {id, error}, where fn names a function in
// gcdiagram.editor and args/result are plain JSON-like data (PDF bytes arrive as a
// Uint8Array).

import type { PyodideAPI } from "pyodide";

interface Request {
  id: number;
  fn: string;
  args: unknown[];
}

const LIB = "/home/pyodide/lib";

async function start(): Promise<{ py: PyodideAPI; editor: Record<string, unknown> }> {
  const base = new URL(import.meta.env.BASE_URL, self.location.origin);
  const pyodideUrl = new URL("pyodide/", base).href;
  const { loadPyodide } = (await import(/* @vite-ignore */ `${pyodideUrl}pyodide.mjs`)) as {
    loadPyodide: (options: { indexURL: string }) => Promise<PyodideAPI>;
  };
  const py = await loadPyodide({ indexURL: pyodideUrl });
  const sources = (await (await fetch(new URL("gcdiagram-sources.json", base))).json()) as Record<string, string>;
  for (const [path, text] of Object.entries(sources)) {
    const full = `${LIB}/${path}`;
    py.FS.mkdirTree(full.slice(0, full.lastIndexOf("/")));
    py.FS.writeFile(full, text);
  }
  py.runPython(`import sys; sys.path.insert(0, ${JSON.stringify(LIB)})`);
  return { py, editor: py.pyimport("gcdiagram.editor") as unknown as Record<string, unknown> };
}

const ready = start();
ready.then(
  () => self.postMessage({ id: 0, result: "ready" }),
  (e: unknown) => self.postMessage({ id: 0, error: String(e) }),
);

type PyResult = { toJs?: (o: object) => unknown; destroy?: () => void };

self.onmessage = async (event: MessageEvent<Request>) => {
  const { id, fn, args } = event.data;
  try {
    const { py, editor } = await ready;
    const func = editor[fn] as ((...a: unknown[]) => unknown) | undefined;
    if (typeof func !== "function") throw new Error(`no editor function ${fn}`);
    const pyArgs = args.map((a) => (a !== null && typeof a === "object" ? py.toPy(a) : a));
    const raw = func(...pyArgs) as PyResult | string | number;
    for (const a of pyArgs) (a as PyResult)?.destroy?.();
    let result: unknown = raw;
    if (raw && typeof raw === "object" && raw.toJs) {
      result = raw.toJs({ dict_converter: Object.fromEntries, create_pyproxies: false });
      raw.destroy?.();
    }
    self.postMessage({ id, result });
  } catch (e) {
    self.postMessage({ id, error: e instanceof Error ? e.message : String(e) });
  }
};
