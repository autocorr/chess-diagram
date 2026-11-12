// Promise-based client for the Pyodide worker. Each method calls the function of the
// same name in gcdiagram.editor (src/gcdiagram/editor.py).

export interface PieceInfo {
  token: string;
  kind: string;
  color: "white" | "black" | "neutral";
  variant: "plain" | "chameleon" | "mirror";
  angle: number;
}

export interface Info {
  pieces: PieceInfo[];
  /** special name -> palette color -> FEN token, for the colors the fonts have */
  specials: Record<string, Partial<Record<string, string>>>;
  /** How label annotations are drawn (gcdiagram/geometry.py), in font units. */
  label: LabelInfo;
}

export interface LabelInfo {
  /** the characters a label can show */
  chars: string;
  /** font family (bold) and size */
  font: string;
  size: number;
  /** width of the white outline */
  halo: number;
  /** annotation color -> fill */
  fills: Record<string, string>;
  /** corner -> where its label goes, from the square's top-left corner */
  corners: Record<string, { x: number; y: number; anchor: string }>;
}

/** A parsed annotation (gcdiagram/annotations.py), with its canonical text form. */
export interface Annotation {
  spec: string;
  kind: string;
  /** ["e4"], or ["e2", "e4"] for an arrow */
  squares: string[];
  color: string;
  /** labels only: "tl", "tr", "bl" or "br", and one character; "" otherwise */
  corner: string;
  symbol: string;
}

export interface Failure {
  error: string;
  code: string;
}

export interface Rendered {
  fen: string;
  svg: string;
  width: number;
  height: number;
  boardX: number;
  boardY: number;
  files: number;
  ranks: number;
  cells: string[][];
  /** state.options.annotations, parsed, in the same order */
  annotations: Annotation[];
}

export type Options = Record<string, unknown>;

export const failed = (r: object): r is Failure => "error" in r;

export class Python {
  private worker: Worker;
  private next = 1;
  private pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  readonly ready: Promise<void>;

  constructor() {
    this.worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
    let markReady!: () => void;
    let markFailed!: (e: Error) => void;
    this.ready = new Promise((resolve, reject) => {
      markReady = resolve;
      markFailed = reject;
    });
    this.worker.onmessage = (event: MessageEvent<{ id: number; result?: unknown; error?: string }>) => {
      const { id, result, error } = event.data;
      if (id === 0) {
        if (error) markFailed(new Error(error));
        else markReady();
        return;
      }
      const call = this.pending.get(id);
      this.pending.delete(id);
      if (error !== undefined) call?.reject(new Error(error));
      else call?.resolve(result);
    };
  }

  private call<T>(fn: string, ...args: unknown[]): Promise<T> {
    const id = this.next++;
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject });
      this.worker.postMessage({ id, fn, args });
    });
  }

  info = () => this.call<Info>("info");
  render = (fen: string, options: Options) => this.call<Rendered | Failure>("render", fen, options);
  setCell = (fen: string, square: string, token: string) =>
    this.call<{ fen: string } | Failure>("set_cell", fen, square, token);
  move = (fen: string, from: string, to: string) => this.call<{ fen: string } | Failure>("move", fen, from, to);
  rotate = (fen: string, square: string, step: number) =>
    this.call<{ fen: string } | Failure>("rotate", fen, square, step);
  recolor = (fen: string, square: string) => this.call<{ fen: string } | Failure>("recolor", fen, square);
  resize = (fen: string, width: number, height: number, annotations: string[]) =>
    this.call<{ fen: string; annotations: string[] } | Failure>("resize", fen, width, height, annotations);
  toggleAnnotation = (
    annotations: string[],
    kind: string,
    squares: string[],
    color: string,
    corner: string,
    symbol: string,
  ) =>
    this.call<{ annotations: string[] } | Failure>(
      "toggle_annotation",
      annotations,
      kind,
      squares,
      color,
      corner,
      symbol,
    );
  export = (fen: string, options: Options, fmt: string) =>
    this.call<{ data: string | Uint8Array; mime: string } | Failure>("export", fen, options, fmt);
  figureSvg = (token: string, shade: string) => this.call<string>("figure_svg", token, shade);
}
