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

test("dark mode follows the system until switched, and the switch is remembered", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await open(page);
  const html = page.locator("html");
  const toggle = page.getByTestId("theme-toggle");
  await expect(html).toHaveAttribute("data-theme", "dark");
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  const background = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  const dark = await background();
  // The board and palette icons are dimmed on screen...
  const look = () =>
    page.evaluate(() => ({
      paper: getComputedStyle(document.getElementById("board")!).backgroundColor,
      board: getComputedStyle(document.querySelector("#board svg")!).filter,
      icon: getComputedStyle(document.querySelector("#pieces button svg")!).filter,
    }));
  expect(await look()).toEqual({ paper: "rgb(214, 214, 214)", board: "brightness(0.84)", icon: "brightness(0.84)" });
  // ...but exports are still exactly what the CLI writes.
  const download = page.waitForEvent("download");
  await page.locator('[data-export="svg"]').click();
  const exported = readFileSync((await (await download).path())!);
  expect(exported.equals(execFileSync("uv", ["run", "gcdiagram", START, "-f", "svg"], { cwd: REPO }))).toBe(true);
  await toggle.click();
  expect(await look()).toEqual({ paper: "rgb(255, 255, 255)", board: "none", icon: "none" });
  await expect(html).toHaveAttribute("data-theme", "light");
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  expect(await background()).not.toBe(dark);
  // A saved choice beats the system setting.
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", "light");
  await expect(page.getByTestId("theme-toggle")).toHaveAttribute("aria-checked", "false");
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

test("Mirrored offers the knight at the angles the fonts have", async ({ page }) => {
  await open(page);
  await setFen(page, EMPTY8);
  await choose(page, "color", "black");
  await choose(page, "variant", "mirror"); // the queen has no mirrored glyphs: move to the knight
  await expect(page.getByTestId("selection")).toHaveText("Selected: {!n90}");
  await expect(page.locator("#pieces button:enabled")).toHaveCount(1);
  await expect(page.locator('[data-testid="piece-N"]')).toHaveAttribute("aria-pressed", "true");
  for (const a of ["0", "45", "135", "225", "315"]) {
    await expect(page.locator(`input[name="angle"][value="${a}"]`)).toBeDisabled();
  }
  await choose(page, "angle", "270");
  await expect(page.getByTestId("selection")).toHaveText("Selected: {!n270}");
  await clickSquare(page, "e4");
  await expect(fen(page)).toHaveValue("8/8/8/8/4{!n270}3/8/8/8");
  // Back to plain: the knight and its angle carry over.
  await choose(page, "variant", "plain");
  await expect(page.getByTestId("selection")).toHaveText("Selected: {n270}");
  // An angle the variant lacks snaps to the nearest one: 45 to 90, and 135 (as near 90
  // as 180) clockwise to 180.
  await choose(page, "angle", "45");
  await choose(page, "variant", "mirror");
  await expect(page.getByTestId("selection")).toHaveText("Selected: {!n90}");
  await choose(page, "variant", "plain");
  await choose(page, "angle", "135");
  await choose(page, "variant", "mirror");
  await expect(page.getByTestId("selection")).toHaveText("Selected: {!n180}");
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

test("annotations and diagram options", async ({ page }) => {
  await open(page);
  const annotations = page.getByTestId("annotations");
  const items = annotations.locator(".label");
  await expect(annotations).toHaveText("No annotations");
  // Choosing a shape or colour switches to the Annotate tool.
  await page.getByText("Arrow", { exact: true }).click();
  await expect(page.locator('input[name="tool"][value="annotate"]')).toBeChecked();
  await dragSquares(page, "e2", "e4");
  await expect(items).toHaveText(["arrow e2-e4"]);
  await choose(page, "mark-kind", "circle");
  await choose(page, "mark-color", "vermilion");
  await clickSquare(page, "d1");
  await expect(items).toHaveText(["arrow e2-e4", "circle d1 (orange)"]);
  await expect(page.locator('#board svg path[fill="#D55E00"]')).toHaveCount(1);
  // Every mark is outlined in white.
  await expect(page.locator('#board svg path[stroke="#fff"]')).toHaveCount(2);
  // The same mark in another colour recolours it; in the same colour, removes it.
  await choose(page, "mark-color", "green");
  await clickSquare(page, "d1");
  await expect(items).toHaveText(["arrow e2-e4", "circle d1 (green)"]);
  await expect(page.locator('#board svg path[fill="#009E73"]')).toHaveCount(1);
  await clickSquare(page, "d1");
  await expect(items).toHaveText(["arrow e2-e4"]);
  for (const kind of ["cross", "square", "triangle", "dot"]) {
    await choose(page, "mark-kind", kind);
    await clickSquare(page, "h8");
  }
  await expect(items).toHaveText(["arrow e2-e4", "cross h8 (green)", "square h8 (green)", "triangle h8 (green)", "dot h8 (green)"]);
  await page.getByTestId("border").selectOption("double");
  await page.getByTestId("caption").fill("#2");
  await page.getByTestId("count").check();
  await expect(page.locator("#board svg text")).toHaveText(["#2", "(16+16)"]);
  expect(page.url()).toContain("border=double");
  expect(page.url()).toContain("mark=arrow%3Ae2-e4");
  // The URL restores everything.
  await page.reload();
  await expect(page.locator("body[data-ready]")).toBeAttached({ timeout: 45_000 });
  await expect(page.getByTestId("border")).toHaveValue("double");
  await expect(items).toHaveText(["arrow e2-e4", "cross h8 (green)", "square h8 (green)", "triangle h8 (green)", "dot h8 (green)"]);
  await expect(page.locator("#board svg text")).toHaveText(["#2", "(16+16)"]);
  // Clicking an item removes just that annotation.
  await annotations.getByRole("button", { name: "Remove square h8 (green)" }).click();
  await expect(items).toHaveText(["arrow e2-e4", "cross h8 (green)", "triangle h8 (green)", "dot h8 (green)"]);
  await expect(page.locator('#board svg path[fill="#009E73"]')).toHaveCount(3);
  expect(page.url()).not.toContain("square%3Ah8");
  await page.getByRole("button", { name: "Clear annotations" }).click();
  await expect(annotations).toHaveText("No annotations");
  expect(page.url()).not.toContain("mark=");
});

test("old links with arrow= still show their arrows", async ({ page }) => {
  await open(page, "#arrow=e2-e4");
  await expect(page.getByTestId("annotations").locator(".label")).toHaveText(["arrow e2-e4"]);
});

test("captions above and below, with bold and italic", async ({ page }) => {
  await open(page);
  const above = page.getByTestId("caption-above");
  await above.fill("The Problemist 2024");
  // Select "The Problemist" and make it italic with the button, then bold with Ctrl+B.
  await above.evaluate((el: HTMLTextAreaElement) => el.setSelectionRange(0, 14));
  await page.getByRole("button", { name: "Italic" }).click();
  await expect(above).toHaveValue("<i>The Problemist</i> 2024");
  await page.keyboard.press("Control+b");
  await expect(above).toHaveValue("<i><b>The Problemist</b></i> 2024");
  await page.keyboard.press("Control+b"); // again: unwraps
  await expect(above).toHaveValue("<i>The Problemist</i> 2024");
  await page.getByTestId("caption").fill("<b>#2</b>");
  await idle(page);
  const texts = page.locator("#board svg text");
  await expect(texts).toHaveText(["The Problemist 2024", "#2"]);
  await expect(texts.nth(0).locator('tspan[font-style="italic"]')).toHaveText("The Problemist ");
  await expect(texts.nth(1).locator('tspan[font-weight="bold"]')).toHaveText("#2");
  // Both are left-aligned at the diagram's edge, one above the board and one below.
  const [a, b] = await texts.evaluateAll((els) => els.map((el) => el.getBoundingClientRect()));
  const board = (await page.locator("#board svg use").first().boundingBox())!;
  expect(Math.abs(a!.left - b!.left)).toBeLessThan(1);
  expect(a!.bottom).toBeLessThan(board.y);
  expect(b!.top).toBeGreaterThan(board.y);
  expect(page.url()).toContain("above=");
});

test("the Dark mode switch and the Help link share a centre line", async ({ page }) => {
  await open(page);
  const middle = async (selector: string) => {
    const box = (await page.locator(selector).boundingBox())!;
    return box.y + box.height / 2;
  };
  const label = await middle("#theme-toggle .switch-label");
  expect(Math.abs(label - (await middle("#theme-toggle .switch")))).toBeLessThan(1);
  expect(Math.abs(label - (await middle("#help-link")))).toBeLessThan(1);
});

test("exports are byte-identical to the gcdiagram CLI", async ({ page }) => {
  const position = "4k3/8/8/2{Q90}5/8/8/8/4K3";
  const marks = ["arrow:e1-e8", "circle:c5:vermilion", "cross:e8", "triangle:a1:green", "square:h1:blue"];
  await open(
    page,
    `#fen=${encodeURIComponent(position)}&border=double&above=${encodeURIComponent("<i>J. Smith</i>")}` +
      `&caption=${encodeURIComponent("<b>#2</b>")}&count=1&${marks.map((m) => `mark=${m}`).join("&")}`,
  );
  for (const fmt of ["svg", "pdf", "tex"]) {
    const download = page.waitForEvent("download");
    await page.locator(`[data-export="${fmt}"]`).click();
    const file = await download;
    expect(file.suggestedFilename()).toBe(`diagram.${fmt}`);
    const browser = readFileSync((await file.path())!);
    const cli = execFileSync(
      "uv",
      [
        "run", "gcdiagram", position, "-f", fmt, "-b", "double", "-C", "<i>J. Smith</i>",
        "-c", "<b>#2</b>", "-n", ...marks.flatMap((m) => ["-m", m]),
      ],
      { cwd: REPO },
    );
    expect(browser.equals(cli), `${fmt} export differs from the CLI`).toBe(true);
  }
});

test("PNG export is drawn from the SVG at the chosen resolution", async ({ page }) => {
  await open(page, "#mark=circle:e4:blue");
  await page.getByTestId("png-dpi").selectOption("150");
  const download = page.waitForEvent("download");
  await page.locator('[data-export="png"]').click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("diagram.png");
  const png = readFileSync((await file.path())!);
  expect(png.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))).toBe(true);
  // 8 squares of 20pt plus a 1pt frame each side is 162pt: 337.5px at 150 dpi.
  expect([png.readUInt32BE(16), png.readUInt32BE(20)]).toEqual([338, 338]);
  // Sample pixels: the frame is black, an empty light square white, the circle blue.
  const pixels = await page.evaluate(async (data) => {
    const bitmap = await createImageBitmap(new Blob([Uint8Array.from(atob(data), (c) => c.charCodeAt(0))]));
    const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(bitmap, 0, 0);
    const px = (pt: [number, number]) => [...ctx.getImageData((pt[0] * 150) / 72, (pt[1] * 150) / 72, 1, 1).data];
    // e4's centre is at 1 + 4.5 * 20 = 91pt; the circle's ring is 0.37 squares out.
    return { frame: px([0.5, 0.5]), light: px([91 - 4, 91]), ring: px([91 + 20 * 0.405, 91]) };
  }, png.toString("base64"));
  expect(pixels.frame).toEqual([0, 0, 0, 255]);
  expect(pixels.light).toEqual([255, 255, 255, 255]);
  expect(pixels.ring).toEqual([0, 114, 178, 255]);
});

// --- Small screens ------------------------------------------------------------------------

const SCREENS: [string, number, number][] = [
  ["small phone, portrait", 375, 667],
  ["small phone, landscape", 667, 375],
  ["phone, portrait", 390, 844],
  ["phone, landscape", 844, 390],
  ["tablet, portrait", 768, 1024],
  ["tablet, landscape", 1024, 768],
  ["desktop", 1400, 900],
];

for (const [name, width, height] of SCREENS) {
  test.describe(name, () => {
    test.use({ viewport: { width, height }, hasTouch: name !== "desktop" });

    test("the board stays in view while the controls are used", async ({ page }) => {
      await open(page);
      const layout = (id: string) =>
        page.evaluate((id) => {
          const el = document.getElementById(id)!;
          el.scrollIntoView({ block: "end" });
          const r = el.getBoundingClientRect();
          const board = document.getElementById("board")!.getBoundingClientRect();
          const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
          return {
            pageScrollsSideways: document.documentElement.scrollWidth > innerWidth,
            boardInView: board.top >= -1 && board.bottom <= innerHeight + 1 && board.left >= 0 && board.right <= innerWidth,
            controlUncovered: hit !== null && el.contains(hit),
          };
        }, id);
      const expected = { pageScrollsSideways: false, boardInView: true, controlUncovered: true };
      expect(await layout("specials")).toEqual(expected);
      expect(await layout("square-size")).toEqual(expected);
    });
  });
}

test.describe("touch", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  async function longPress(page: Page, square: string): Promise<void> {
    const { x, y } = await centre(page, square);
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
    await page.waitForTimeout(700);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  }

  test("long-press opens a menu that rotates and clears", async ({ page }) => {
    await open(page);
    await setFen(page, "8/8/8/8/4Q3/8/8/7{@star}");
    const menu = page.getByTestId("square-menu");
    await longPress(page, "d4"); // empty: nothing to act on
    await expect(menu).toBeHidden();
    await expect(fen(page)).toHaveValue("8/8/8/8/4Q3/8/8/7{@star}");

    await longPress(page, "e4");
    await expect(menu).toBeVisible();
    await expect(fen(page)).toHaveValue("8/8/8/8/4Q3/8/8/7{@star}"); // the press itself placed nothing
    await page.getByRole("button", { name: "Rotate clockwise" }).tap();
    await expect(fen(page)).toHaveValue("8/8/8/8/4{Q45}3/8/8/7{@star}");
    await page.getByRole("button", { name: "Rotate anticlockwise" }).tap();
    await expect(fen(page)).toHaveValue("8/8/8/8/4Q3/8/8/7{@star}");
    const recolor = page.getByRole("button", { name: "Change colour" });
    await recolor.tap();
    await expect(fen(page)).toHaveValue("8/8/8/8/4q3/8/8/7{@star}");
    await recolor.tap();
    await expect(fen(page)).toHaveValue("8/8/8/8/4{=Q}3/8/8/7{@star}");
    await recolor.tap();
    await expect(fen(page)).toHaveValue("8/8/8/8/4Q3/8/8/7{@star}");
    // A tap elsewhere on the board only closes the menu.
    const a1 = await centre(page, "a1");
    await page.touchscreen.tap(a1.x, a1.y);
    await expect(menu).toBeHidden();
    await idle(page);
    await expect(fen(page)).toHaveValue("8/8/8/8/4Q3/8/8/7{@star}");

    await longPress(page, "h1"); // special figures don't rotate, but a star has two colours
    await expect(page.getByRole("button", { name: "Rotate clockwise" })).toBeHidden();
    await recolor.tap();
    await expect(fen(page)).toHaveValue("8/8/8/8/4Q3/8/8/7{@Star}");
    await page.getByRole("button", { name: "Clear square" }).tap();
    await expect(menu).toBeHidden();
    await expect(fen(page)).toHaveValue("8/8/8/8/4Q3/8/8/8");
  });

  test("tapping places and touch-dragging moves", async ({ page }) => {
    await open(page);
    await setFen(page, EMPTY8);
    const e4 = await centre(page, "e4");
    await page.touchscreen.tap(e4.x, e4.y);
    await expect(fen(page)).toHaveValue("8/8/8/8/4Q3/8/8/8");
    const e5 = await centre(page, "e5");
    const cdp = await page.context().newCDPSession(page);
    const touch = (type: string, points: { x: number; y: number }[]) =>
      cdp.send("Input.dispatchTouchEvent", { type: type as "touchStart", touchPoints: points });
    await touch("touchStart", [e4]);
    for (let i = 1; i <= 5; i++) await touch("touchMove", [{ x: e4.x, y: e4.y + ((e5.y - e4.y) * i) / 5 }]);
    await touch("touchEnd", []);
    await expect(fen(page)).toHaveValue("8/8/8/4Q3/8/8/8/8");
  });
});
