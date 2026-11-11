import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { type Page, expect, test } from "@playwright/test";

const REPO = fileURLToPath(new URL("../..", import.meta.url));
const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR";
const EMPTY8 = "8/8/8/8/8/8/8/8";
const U = 2000;
const FRAME: Record<string, number> = { single: 100, double: 350, outline: 100, none: 0 };

async function open(page: Page, hash = ""): Promise<void> {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`/${hash}`);
  await expect(page.locator("body[data-ready]")).toBeAttached({ timeout: 45_000 });
  expect(errors).toEqual([]);
}

const fen = (page: Page) => page.getByTestId("fen");

/** Wait until the editor has finished all queued work (and so re-rendered the board). */
async function idle(page: Page): Promise<void> {
  await expect(page.locator("body[data-busy]")).toHaveCount(0);
}

/** Set the FEN by typing it, as a user would, and wait for the board to follow. */
async function setFen(page: Page, value: string, canonical = value): Promise<void> {
  await fen(page).fill(value);
  await fen(page).blur();
  await expect(fen(page)).toHaveValue(canonical);
  await idle(page);
}

/** Viewport coordinates of the centre of a square, from the rendered SVG's geometry. */
async function centre(page: Page, square: string, border = "single"): Promise<{ x: number; y: number }> {
  await idle(page);
  const svg = page.locator("#board svg");
  const box = (await svg.boundingBox())!;
  const viewBox = (await svg.getAttribute("viewBox"))!.split(" ").map(Number);
  const ranks = (await fen(page).inputValue()).split("/").length;
  const scale = box.width / viewBox[2]!;
  const col = square.charCodeAt(0) - 97;
  const row = ranks - Number(square.slice(1));
  const offset = FRAME[border]!;
  return {
    x: box.x + (offset + (col + 0.5) * U) * scale,
    y: box.y + (offset + (row + 0.5) * U) * scale,
  };
}

async function clickSquare(page: Page, square: string, button: "left" | "right" = "left"): Promise<void> {
  const { x, y } = await centre(page, square);
  await page.mouse.click(x, y, { button });
}

async function dragSquares(page: Page, from: string, to: string): Promise<void> {
  const a = await centre(page, from);
  const b = await centre(page, to);
  await page.mouse.move(a.x, a.y);
  await page.mouse.down();
  await page.mouse.move(b.x, b.y, { steps: 5 });
  await page.mouse.up();
}

async function choose(page: Page, group: string, value: string): Promise<void> {
  await page.locator(`input[name="${group}"][value="${value}"]`).check({ force: true });
}

test("starts Python and shows the start position", async ({ page }) => {
  await open(page);
  await expect(page.getByTestId("status")).toHaveText("Ready");
  await expect(fen(page)).toHaveValue(START);
  // 32 pieces + 16 empty dark squares; blank light squares are not drawn.
  await expect(page.locator("#board svg use")).toHaveCount(48);
});

test("the Help link opens and closes a modal", async ({ page }) => {
  await open(page);
  await expect(page).toHaveTitle("Chess Diagram Editor");
  const help = page.getByTestId("help");
  await expect(help).toBeHidden();
  const url = page.url();
  await page.getByTestId("help-link").click();
  await expect(help).toBeVisible();
  expect(page.url()).toBe(url); // the hash holds the diagram, so the link mustn't touch it
  await page.keyboard.press("Escape");
  await expect(help).toBeHidden();
  await page.getByTestId("help-link").click();
  await page.getByRole("button", { name: "Close help" }).click();
  await expect(help).toBeHidden();
});

test("typing a FEN validates it and normalises it", async ({ page }) => {
  await open(page);
  await fen(page).fill("8/7");
  await expect(page.getByTestId("fen-error")).toHaveText("rank 2 from the top has 7 squares, the first has 8");
  await expect(fen(page)).toHaveClass(/invalid/);
  await setFen(page, "{Q0}{=q}6/8", "Q{=Q}6/8");
  await expect(page.getByTestId("fen-error")).toHaveText("");
  await expect(page.locator("#board svg use[data-square='b2']")).toHaveCount(1);
  expect(page.url()).toContain(encodeURIComponent("Q{=Q}6/8"));
});

test("places, toggles and clears pieces", async ({ page }) => {
  await open(page);
  await setFen(page, EMPTY8);
  await choose(page, "color", "black");
  await page.locator('[data-testid="piece-R"]').click();
  await choose(page, "angle", "90");
  await expect(page.getByTestId("selection")).toHaveText("Selected: {r90}");
  await clickSquare(page, "e4");
  await expect(fen(page)).toHaveValue("8/8/8/8/4{r90}3/8/8/8");
  await clickSquare(page, "e4"); // same figure again: toggles it off
  await expect(fen(page)).toHaveValue(EMPTY8);
  await clickSquare(page, "a1");
  await clickSquare(page, "a1", "right");
  await expect(fen(page)).toHaveValue(EMPTY8);
});

test("only offers figures the fonts contain", async ({ page }) => {
  await open(page);
  await choose(page, "color", "neutral");
  await choose(page, "variant", "chameleon");
  await expect(page.locator("#pieces button:disabled")).toHaveCount(6);
  await expect(page.getByTestId("selection")).toHaveText("Not available in the GC fonts");
  await choose(page, "variant", "plain");
  await expect(page.locator('input[name="angle"][value="45"]')).toBeDisabled();
  await expect(page.locator('input[name="angle"][value="90"]')).toBeEnabled();
  await expect(page.locator('[data-testid="special-star"]')).toBeDisabled(); // no neutral star
  await expect(page.locator('[data-testid="special-equihopper"]')).toBeEnabled();
  await choose(page, "color", "white");
  await page.locator('[data-testid="special-star"]').click();
  await expect(page.getByTestId("selection")).toHaveText("Selected: {@Star}");
});

test("rotates with R, moves by dragging, deletes with Delete", async ({ page }) => {
  await open(page);
  await setFen(page, "8/8/8/8/4{=N90}3/8/8/8");
  const e4 = await centre(page, "e4");
  await page.mouse.move(e4.x, e4.y);
  await page.keyboard.press("r");
  await expect(fen(page)).toHaveValue("8/8/8/8/4{=N180}3/8/8/8"); // neutral: skips 135
  await page.keyboard.press("Shift+R");
  await expect(fen(page)).toHaveValue("8/8/8/8/4{=N90}3/8/8/8");
  await dragSquares(page, "e4", "a1");
  await expect(fen(page)).toHaveValue("8/8/8/8/8/8/8/{=N90}7");
  const a1 = await centre(page, "a1");
  await page.mouse.move(a1.x, a1.y);
  await page.keyboard.press("Delete");
  await expect(fen(page)).toHaveValue(EMPTY8);
});

test("holes, walls and board size", async ({ page }) => {
  await open(page);
  await setFen(page, EMPTY8);
  await choose(page, "tool", "hole");
  await clickSquare(page, "a1");
  await choose(page, "tool", "wall");
  await clickSquare(page, "b1");
  await expect(fen(page)).toHaveValue("8/8/8/8/8/8/8/.*6");
  await clickSquare(page, "b1"); // toggles the wall off
  await expect(fen(page)).toHaveValue("8/8/8/8/8/8/8/.7");
  await page.getByTestId("files").fill("10");
  await page.getByTestId("files").press("Enter");
  await page.getByTestId("ranks").fill("3");
  await page.getByTestId("ranks").press("Enter");
  await expect(fen(page)).toHaveValue("10/10/.9");
});

test("arrows and diagram options", async ({ page }) => {
  await open(page);
  await choose(page, "tool", "arrow");
  await dragSquares(page, "e2", "e4");
  await expect(page.getByTestId("arrows")).toHaveText("Arrows: e2-e4");
  await expect(page.locator('#board svg path[fill-opacity=".6"]')).toHaveCount(1);
  await page.getByTestId("border").selectOption("double");
  await page.getByTestId("caption").fill("#2");
  await page.getByTestId("count").check();
  await expect(page.locator("#board svg text")).toHaveText(["#2", "(16+16)"]);
  expect(page.url()).toContain("border=double");
  expect(page.url()).toContain("arrow=e2-e4");
  // The URL restores everything.
  await page.reload();
  await expect(page.locator("body[data-ready]")).toBeAttached({ timeout: 45_000 });
  await expect(page.getByTestId("border")).toHaveValue("double");
  await expect(page.getByTestId("arrows")).toHaveText("Arrows: e2-e4");
  await expect(page.locator("#board svg text")).toHaveText(["#2", "(16+16)"]);
});

test("exports are byte-identical to the gcdiagram CLI", async ({ page }) => {
  const position = "4k3/8/8/2{Q90}5/8/8/8/4K3";
  await open(page, `#fen=${encodeURIComponent(position)}&border=double&caption=%232&count=1&arrow=e1-e8`);
  for (const fmt of ["svg", "pdf", "tex"]) {
    const download = page.waitForEvent("download");
    await page.locator(`[data-export="${fmt}"]`).click();
    const file = await download;
    expect(file.suggestedFilename()).toBe(`diagram.${fmt}`);
    const browser = readFileSync((await file.path())!);
    const cli = execFileSync(
      "uv",
      ["run", "gcdiagram", position, "-f", fmt, "-b", "double", "-c", "#2", "-n", "-a", "e1-e8"],
      { cwd: REPO },
    );
    expect(browser.equals(cli), `${fmt} export differs from the CLI`).toBe(true);
  }
});
