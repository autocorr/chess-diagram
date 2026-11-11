// Editor UI. All chess and diagram logic runs in Python (gcdiagram.editor via Pyodide);
// this file only handles the DOM, pointer and keyboard input, and the URL hash.

import { type Failure, type Info, type Options, Python, type Rendered, failed } from "./python";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR";
const U = 2000; // font units per square in the rendered SVG
const FILES = "abcdefghijklmnopqrstuvwxyz";
const KINDS = ["K", "Q", "R", "B", "N", "P"];
const ANGLES = [0, 45, 90, 135, 180, 225, 270, 315];
const SVG_NS = "http://www.w3.org/2000/svg";
const LONG_PRESS_MS = 450;

interface DiagramOptions extends Options {
  border: string;
  wall: string;
  caption: string[];
  piece_count: boolean;
  arrows: string[];
  square_size: number;
}

interface State {
  fen: string;
  options: DiagramOptions;
}

type Selection = { type: "piece"; kind: string } | { type: "special"; name: string };

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const boardEl = $<HTMLDivElement>("board");
const fenInput = $<HTMLInputElement>("fen");
const fenError = $<HTMLParagraphElement>("fen-error");
const statusEl = $<HTMLSpanElement>("status");

const py = new Python();
let info: Info = { pieces: [], specials: {} };
let state = loadHash();
let view: Rendered | null = null;
let tool = "place";
let color = "white";
let variant = "plain";
let angle = 0;
let selection: Selection = { type: "piece", kind: "Q" };
let hover: string | null = null;
let pressed: string | null = null;
let pointerType = "mouse"; // of the last pointerdown on the board
let longPress: ReturnType<typeof setTimeout> | undefined;
let menuSquare: string | null = null; // the square the touch menu is open for
let queue: Promise<unknown> = Promise.resolve();
const icons = new Map<string, string>();

let pendingActions = 0;

/**
 * Run actions one at a time, in order, so quick successive edits cannot race.
 * body[data-busy] is set while any are pending (the end-to-end tests wait on it).
 */
function enqueue(action: () => Promise<void>): Promise<void> {
  pendingActions += 1;
  document.body.dataset.busy = "true";
  const run = queue.then(action, action).finally(() => {
    pendingActions -= 1;
    if (pendingActions === 0) delete document.body.dataset.busy;
  });
  queue = run.catch((e: unknown) => setStatus(String(e), true));
  return run;
}

function setStatus(text: string, error = false): void {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", error);
}

// --- URL hash ---------------------------------------------------------------------------

function loadHash(): State {
  const p = new URLSearchParams(location.hash.slice(1));
  return {
    fen: p.get("fen") || START,
    options: {
      border: p.get("border") ?? "single",
      wall: p.get("wall") ?? "solid",
      caption: p.getAll("caption"),
      piece_count: p.get("count") === "1",
      arrows: p.getAll("arrow"),
      square_size: Number(p.get("size") ?? 20) || 20,
    },
  };
}

function saveHash(): void {
  const p = new URLSearchParams({ fen: state.fen });
  const o = state.options;
  if (o.border !== "single") p.set("border", o.border);
  if (o.wall !== "solid") p.set("wall", o.wall);
  for (const line of o.caption) p.append("caption", line);
  if (o.piece_count) p.set("count", "1");
  for (const arrow of o.arrows) p.append("arrow", arrow);
  if (o.square_size !== 20) p.set("size", String(o.square_size));
  history.replaceState(null, "", `#${p}`);
}

// --- Rendering --------------------------------------------------------------------------

/** Render a FEN (by default the current one) and, if it is valid, make it current. */
async function refresh(fen = state.fen): Promise<void> {
  const result = await py.render(fen, state.options);
  if (failed(result)) {
    showError(result.error);
    return;
  }
  view = result;
  state.fen = result.fen;
  showError("");
  draw();
  syncControls();
  saveHash();
}

function showError(message: string): void {
  fenError.textContent = message;
  fenInput.classList.toggle("invalid", message !== "");
}

function draw(): void {
  if (!view) return;
  boardEl.innerHTML = view.svg;
  const svg = boardEl.querySelector("svg")!;
  const mark = document.createElementNS(SVG_NS, "rect");
  mark.id = "hover";
  mark.setAttribute("width", String(U));
  mark.setAttribute("height", String(U));
  mark.setAttribute("fill", "var(--hover)");
  mark.setAttribute("pointer-events", "none");
  mark.setAttribute("visibility", "hidden");
  svg.append(mark);
  showHover();
  if (menuSquare) openMenu(menuSquare); // re-check and re-place it against the new board
}

function showHover(): void {
  const mark = boardEl.querySelector<SVGRectElement>("#hover");
  if (!mark || !view) return;
  const square = hover ?? menuSquare;
  const pos = square ? position(square) : null;
  if (!pos) {
    mark.setAttribute("visibility", "hidden");
    return;
  }
  mark.setAttribute("x", String(view.boardX + pos[1] * U));
  mark.setAttribute("y", String(view.boardY + pos[0] * U));
  mark.setAttribute("visibility", "visible");
}

function syncControls(): void {
  if (!view) return;
  // Never overwrite a field the user is typing in.
  const set = (id: string, value: string) => {
    const el = $<HTMLInputElement>(id);
    if (document.activeElement !== el) el.value = value;
  };
  const o = state.options;
  set("fen", view.fen);
  set("files", String(view.files));
  set("ranks", String(view.ranks));
  set("border", o.border);
  set("wall", o.wall);
  set("caption", o.caption.join("\n"));
  set("square-size", String(o.square_size));
  $<HTMLInputElement>("count").checked = o.piece_count;
  $("arrows").textContent = o.arrows.length
    ? `Arrows: ${o.arrows.join(", ")}`
    : "No arrows (drag with the Arrow tool)";
}

// --- Squares ----------------------------------------------------------------------------

/** [row, col] of a square name on the current board, or null if it is off the board. */
function position(square: string): [number, number] | null {
  if (!view) return null;
  const m = /^([a-z])(\d+)$/.exec(square);
  if (!m) return null;
  const col = FILES.indexOf(m[1]!);
  const row = view.ranks - Number(m[2]);
  return col < view.files && row >= 0 && row < view.ranks ? [row, col] : null;
}

function squareAt(event: MouseEvent): string | null {
  const svg = boardEl.querySelector("svg");
  const ctm = svg?.getScreenCTM();
  if (!view || !ctm) return null;
  const p = new DOMPoint(event.clientX, event.clientY).matrixTransform(ctm.inverse());
  const col = Math.floor((p.x - view.boardX) / U);
  const row = Math.floor((p.y - view.boardY) / U);
  if (col < 0 || col >= view.files || row < 0 || row >= view.ranks) return null;
  return `${FILES[col]}${view.ranks - row}`;
}

function cellAt(square: string): string {
  const pos = position(square);
  return pos && view ? view.cells[pos[0]]![pos[1]]! : "";
}

/** The client-coordinate rectangle of a square, for placing the touch menu. */
function squareRect(square: string): DOMRect | null {
  const pos = position(square);
  const ctm = boardEl.querySelector("svg")?.getScreenCTM();
  if (!pos || !view || !ctm) return null;
  const a = new DOMPoint(view.boardX + pos[1] * U, view.boardY + pos[0] * U).matrixTransform(ctm);
  const b = new DOMPoint(view.boardX + (pos[1] + 1) * U, view.boardY + (pos[0] + 1) * U).matrixTransform(ctm);
  return new DOMRect(a.x, a.y, b.x - a.x, b.y - a.y);
}

// --- Touch menu -------------------------------------------------------------------------
// Touch screens have no hover, keyboard or right-click, so a long-press on a figure opens
// a small menu that rotates or removes it.

const menu = $<HTMLDivElement>("square-menu");

function openMenu(square: string): void {
  const cell = cellAt(square);
  const rect = squareRect(square);
  if (cell === "" || !rect) {
    closeMenu();
    return;
  }
  menuSquare = square;
  // Holes, walls and special figures have no rotations; holes, walls and single-version
  // specials (box, cross, half-circle) have no colours.
  const figure = cell !== "." && cell !== "*";
  const special = /@([a-z-]+)/.exec(cell)?.[1];
  const versions = special ? new Set(Object.values(info.specials[special] ?? {})).size : 3;
  for (const b of menu.querySelectorAll<HTMLButtonElement>("[data-rotate]")) b.hidden = !figure || !!special;
  $("menu-recolor").hidden = !figure || versions < 2;
  menu.hidden = false;
  // Above the square if there is room (a finger covers the square itself), else below.
  const m = menu.getBoundingClientRect();
  const gap = 8;
  const top = rect.top - m.height - gap >= gap ? rect.top - m.height - gap : rect.bottom + gap;
  const left = Math.min(Math.max(rect.left + rect.width / 2 - m.width / 2, gap), innerWidth - m.width - gap);
  menu.style.top = `${top}px`;
  menu.style.left = `${left}px`;
  showHover();
}

function closeMenu(): void {
  if (menuSquare === null) return;
  menuSquare = null;
  menu.hidden = true;
  showHover();
}

function cancelLongPress(): void {
  clearTimeout(longPress);
  longPress = undefined;
}

// --- Editing ----------------------------------------------------------------------------

async function apply(result: { fen: string } | Failure): Promise<void> {
  if (failed(result)) {
    setStatus(result.error, true);
    return;
  }
  state.fen = result.fen;
  await refresh();
}

function edit(square: string, token: string): Promise<void> {
  return enqueue(async () => apply(await py.setCell(state.fen, square, token)));
}

function click(square: string): void {
  const current = cellAt(square);
  if (tool === "place") {
    const token = selectedToken();
    if (!token) {
      setStatus("The GC fonts have no glyph for this selection", true);
      return;
    }
    void edit(square, current === token ? "" : token);
  } else if (tool === "erase") {
    void edit(square, "");
  } else if (tool === "hole") {
    void edit(square, current === "." ? "" : ".");
  } else if (tool === "wall") {
    void edit(square, current === "*" ? "" : "*");
  }
}

function drag(from: string, to: string): void {
  if (tool === "arrow") {
    const spec = `${from}-${to}`;
    const arrows = state.options.arrows;
    state.options.arrows = arrows.includes(spec) ? arrows.filter((a) => a !== spec) : [...arrows, spec];
    void enqueue(refresh);
  } else if (cellAt(from) !== "") {
    void enqueue(async () => apply(await py.move(state.fen, from, to)));
  }
}

function rotate(square: string, step: number): void {
  void enqueue(async () => apply(await py.rotate(state.fen, square, step)));
}

/** Keep only arrows whose squares exist on a width x height board. */
function arrowsWithin(width: number, height: number): string[] {
  return state.options.arrows.filter((spec) =>
    (spec.match(/[a-z]\d+/g) ?? []).every((sq) => FILES.indexOf(sq[0]!) < width && Number(sq.slice(1)) <= height),
  );
}

// --- Palette ----------------------------------------------------------------------------

function pieceToken(kind: string, a = angle): string | null {
  return (
    info.pieces.find((p) => p.kind === kind && p.color === color && p.variant === variant && p.angle === a)
      ?.token ?? null
  );
}

function specialToken(name: string): string | null {
  return info.specials[name]?.[color] ?? null;
}

function selectedToken(): string | null {
  return selection.type === "piece" ? pieceToken(selection.kind) : specialToken(selection.name);
}

async function icon(token: string): Promise<string> {
  let svg = icons.get(token);
  if (svg === undefined) {
    svg = await py.figureSvg(token, "light");
    icons.set(token, svg);
  }
  return svg;
}

function buildPalette(): void {
  const angles = $("angles");
  for (const a of ANGLES) {
    const label = document.createElement("label");
    label.innerHTML = `<input type="radio" name="angle" value="${a}"${a === 0 ? " checked" : ""}/>${a}°`;
    angles.append(label);
  }
  for (const kind of KINDS) {
    $("pieces").append(paletteButton(`piece-${kind}`, kind, { type: "piece", kind }, { kind }));
  }
  for (const name of Object.keys(info.specials)) {
    $("specials").append(paletteButton(`special-${name}`, name, { type: "special", name }, { special: name }));
  }
}

/** A palette button that selects a figure and switches to the Place tool. */
function paletteButton(testid: string, title: string, select: Selection, data: Record<string, string>): HTMLButtonElement {
  const b = document.createElement("button");
  b.type = "button";
  Object.assign(b.dataset, data, { testid });
  b.title = title;
  b.addEventListener("click", () => {
    selection = select;
    tool = "place";
    (document.querySelector('input[name="tool"][value="place"]') as HTMLInputElement).checked = true;
    void updatePalette();
  });
  return b;
}

async function updatePalette(): Promise<void> {
  for (const input of document.querySelectorAll<HTMLInputElement>('input[name="angle"]')) {
    const a = Number(input.value);
    input.disabled = selection.type !== "piece" || pieceToken(selection.kind, a) === null;
    input.checked = a === angle;
  }
  for (const b of document.querySelectorAll<HTMLButtonElement>("#pieces button")) {
    const kind = b.dataset.kind!;
    const token = pieceToken(kind);
    b.disabled = token === null;
    b.setAttribute("aria-pressed", String(selection.type === "piece" && selection.kind === kind));
    b.innerHTML = await icon(token ?? kind);
  }
  for (const b of document.querySelectorAll<HTMLButtonElement>("#specials button")) {
    const name = b.dataset.special!;
    const token = specialToken(name);
    b.disabled = token === null;
    b.setAttribute("aria-pressed", String(selection.type === "special" && selection.name === name));
    const tokens = info.specials[name] ?? {};
    b.innerHTML = await icon(token ?? tokens.white ?? tokens.neutral ?? tokens.black ?? "");
  }
  const token = selectedToken();
  $("selection").textContent = token ? `Selected: ${token}` : "Not available in the GC fonts";
}

// --- Event wiring -----------------------------------------------------------------------

function bindRadios(name: string, set: (value: string) => void): void {
  for (const input of document.querySelectorAll<HTMLInputElement>(`input[name="${name}"]`)) {
    input.addEventListener("change", () => {
      if (input.checked) set(input.value);
    });
  }
}

function bindOption(id: string, read: (el: HTMLInputElement) => void): void {
  $<HTMLInputElement>(id).addEventListener("change", (e) => {
    read(e.currentTarget as HTMLInputElement);
    void enqueue(refresh);
  });
}

function wire(): void {
  boardEl.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    pointerType = e.pointerType;
    pressed = squareAt(e);
    if (!pressed) return;
    boardEl.setPointerCapture(e.pointerId);
    if (e.pointerType !== "mouse") {
      const square = pressed;
      longPress = setTimeout(() => {
        longPress = undefined;
        if (pressed !== square) return;
        pressed = null; // the press is used up: no place or move when the finger lifts
        navigator.vibrate?.(10);
        openMenu(square);
      }, LONG_PRESS_MS);
    }
  });
  boardEl.addEventListener("pointermove", (e) => {
    const sq = squareAt(e);
    if (sq !== hover) {
      hover = sq;
      if (sq !== pressed) cancelLongPress(); // moved off the square: it's a drag
      showHover();
    }
  });
  boardEl.addEventListener("pointerleave", () => {
    hover = null;
    showHover();
  });
  boardEl.addEventListener("pointerup", (e) => {
    cancelLongPress();
    if (e.button !== 0 || !pressed) return;
    const released = squareAt(e);
    const from = pressed;
    pressed = null;
    if (!released) return;
    if (released === from) click(from);
    else drag(from, released);
  });
  boardEl.addEventListener("pointercancel", () => {
    cancelLongPress();
    pressed = null;
  });
  boardEl.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    // Android reports a long-press as a context menu; touch has its own menu instead.
    if (pointerType !== "mouse") return;
    const sq = squareAt(e);
    if (sq) void edit(sq, "");
  });

  for (const b of menu.querySelectorAll<HTMLButtonElement>("[data-rotate]")) {
    b.addEventListener("click", () => {
      if (menuSquare) rotate(menuSquare, Number(b.dataset.rotate));
    });
  }
  $("menu-recolor").addEventListener("click", () => {
    const square = menuSquare;
    if (square) void enqueue(async () => apply(await py.recolor(state.fen, square)));
  });
  $("menu-clear").addEventListener("click", () => {
    if (menuSquare) void edit(menuSquare, "");
    closeMenu();
  });
  // Any press outside the menu closes it. On the board that is all it does, so a tap to
  // dismiss the menu doesn't also place a figure.
  document.addEventListener(
    "pointerdown",
    (e) => {
      if (!menuSquare || menu.contains(e.target as Node)) return;
      closeMenu();
      if (boardEl.contains(e.target as Node)) e.stopPropagation();
    },
    true,
  );
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeMenu();
  });
  addEventListener("resize", closeMenu);
  addEventListener("scroll", closeMenu, true);
  // Theme: the page script in index.html picks the starting theme (a saved choice, else
  // the system's). Flipping the switch saves a choice; without one, follow the system.
  const themeToggle = $("theme-toggle");
  const systemDark = matchMedia("(prefers-color-scheme: dark)");
  const setTheme = (dark: boolean) => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    themeToggle.setAttribute("aria-checked", String(dark));
  };
  setTheme(document.documentElement.dataset.theme === "dark");
  themeToggle.addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme !== "dark";
    setTheme(dark);
    try {
      localStorage.setItem("theme", dark ? "dark" : "light");
    } catch {
      // Storage can be unavailable (private windows); the switch still works for this page.
    }
  });
  systemDark.addEventListener("change", (e) => {
    let saved: string | null = null;
    try {
      saved = localStorage.getItem("theme");
    } catch {}
    if (!saved) setTheme(e.matches);
  });

  // Help: a modal dialog. The link doesn't navigate, because the URL hash holds the diagram.
  const help = $("help") as HTMLDialogElement;
  $("help-link").addEventListener("click", (e) => {
    e.preventDefault();
    help.showModal();
  });
  $("help-close").addEventListener("click", () => help.close());
  help.addEventListener("click", (e) => {
    if (e.target === help) help.close(); // a click on the backdrop
  });

  document.addEventListener("keydown", (e) => {
    const target = e.target as HTMLElement;
    if (target.closest("input, textarea, select, dialog") || !hover) return;
    if (e.key === "r" || e.key === "R") {
      e.preventDefault();
      rotate(hover, e.shiftKey ? -45 : 45);
    } else if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      void edit(hover, "");
    }
  });

  // FEN: validate and preview while typing; normalise when the field is left.
  fenInput.addEventListener("input", () => {
    const text = fenInput.value;
    void enqueue(() => refresh(text));
  });
  fenInput.addEventListener("change", () => void enqueue(refresh));
  $("copy-fen").addEventListener("click", () => void navigator.clipboard.writeText(state.fen));

  bindRadios("tool", (v) => (tool = v));
  bindRadios("color", (v) => {
    color = v;
    void updatePalette();
  });
  bindRadios("variant", (v) => {
    variant = v;
    void updatePalette();
  });
  $("angles").addEventListener("change", (e) => {
    const input = e.target as HTMLInputElement;
    if (input.name !== "angle" || !input.checked) return;
    angle = Number(input.value);
    void updatePalette();
  });

  const resize = () => {
    const width = Number($<HTMLInputElement>("files").value);
    const height = Number($<HTMLInputElement>("ranks").value);
    if (!(width >= 1 && width <= 26 && height >= 1 && height <= 26)) {
      setStatus("Boards can be 1 to 26 squares in each direction", true);
      return;
    }
    state.options.arrows = arrowsWithin(width, height);
    void enqueue(async () => apply(await py.resize(state.fen, width, height)));
  };
  $("files").addEventListener("change", resize);
  $("ranks").addEventListener("change", resize);
  $("start").addEventListener("click", () => {
    state.fen = START;
    state.options.arrows = [];
    void enqueue(refresh);
  });
  $("clear").addEventListener("click", () => {
    if (!view) return;
    state.fen = Array(view.ranks).fill(String(view.files)).join("/");
    state.options.arrows = [];
    void enqueue(refresh);
  });

  bindOption("border", (el) => (state.options.border = el.value));
  bindOption("wall", (el) => (state.options.wall = el.value));
  bindOption("count", (el) => (state.options.piece_count = el.checked));
  bindOption("square-size", (el) => (state.options.square_size = Number(el.value) || 20));
  $<HTMLTextAreaElement>("caption").addEventListener("input", (e) => {
    state.options.caption = (e.currentTarget as HTMLTextAreaElement).value.split("\n");
    void enqueue(refresh);
  });
  $("clear-arrows").addEventListener("click", () => {
    state.options.arrows = [];
    void enqueue(refresh);
  });

  for (const button of document.querySelectorAll<HTMLButtonElement>("[data-export]")) {
    button.addEventListener("click", () =>
      enqueue(async () => {
        const fmt = button.dataset.export!;
        const result = await py.export(state.fen, state.options, fmt);
        if (failed(result)) {
          setStatus(result.error, true);
          return;
        }
        const blob = new Blob([result.data as BlobPart], { type: result.mime });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `diagram.${fmt}`;
        link.click();
        // Revoking right away can cancel the download in some browsers.
        setTimeout(() => URL.revokeObjectURL(link.href), 60_000);
      }),
    );
  }
}

async function main(): Promise<void> {
  try {
    await py.ready;
    info = await py.info();
  } catch (e) {
    setStatus(`Could not start Python: ${String(e)}`, true);
    return;
  }
  buildPalette();
  wire();
  await updatePalette();
  await enqueue(refresh);
  setStatus("Ready");
  document.body.dataset.ready = "true";
}

void main();
