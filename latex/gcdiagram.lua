-- gcdiagram.lua -- extended FEN to Good Companion (GC2004) chess diagrams for LuaLaTeX.
--
-- A port of the gcdiagram Python package's parser (fen.py), layout (geometry.py) and
-- TeX emitter (render/tex.py). The emitted \gcbox body must match the Python output
-- exactly; tests/test_latex.py checks this, and tests/vectors.json checks the parser.
-- The functions below are pure, so texlua can run them outside TeX.

local catalog = require("gcdiagram-catalog")

local M = {}

local U = 2000
local BASELINE = 1500
local SINGLE = 100
local DOUBLE_THIN, DOUBLE_GAP, DOUBLE_THICK = 50, 100, 200
local ARROW_SHAFT, ARROW_HEAD_LENGTH, ARROW_HEAD_WIDTH = 200, 640, 600
local MAX_SIZE = 26
local FILES = "abcdefghijklmnopqrstuvwxyz"
local ANGLES = { [0] = true, [45] = true, [90] = true, [135] = true,
                 [180] = true, [225] = true, [270] = true, [315] = true }
local PIECE_NAMES = { K = "king", Q = "queen", R = "rook", B = "bishop", N = "knight", P = "pawn" }

-- special name -> set of colors, derived from the catalog keys
local specials = {}
for key in pairs(catalog.glyphs) do
  local name, color = key:match("^special:([^:]+):([^:]+):")
  if name then
    specials[name] = specials[name] or {}
    specials[name][color] = true
  end
end
M.specials = specials

-- Errors -------------------------------------------------------------------------------

local function fen_error(code, message, pos)
  if pos then message = string.format("%s (at character %d)", message, pos + 1) end
  error({ code = code, message = message }, 0)
end

-- Board model ---------------------------------------------------------------------------
-- cell = { t = "square", fig = figure|nil } | { t = "hole" } | { t = "wall" }
-- figure = { type = "piece", kind, color, angle, variant } | { type = "special", name, color }

local EMPTY = { t = "square" }

local function shade(board, r, c) -- r, c are 1-based; a1 (bottom-left) is dark
  local rank_index = board.height - r
  return ((c - 1) + rank_index) % 2 == 0 and "dark" or "light"
end

local function figure_key(fig, sh)
  if fig.type == "piece" then
    return string.format("piece:%s:%s:%d:%s:%s", fig.kind, fig.color, fig.angle, fig.variant, sh)
  end
  return string.format("special:%s:%s:%s", fig.name, fig.color, sh)
end

local function square_name(board, r, c)
  return FILES:sub(c, c) .. tostring(board.height - r + 1)
end

local function is_board_square(board, r, c)
  if r < 1 or r > board.height or c < 1 or c > board.width then return false end
  return board.cells[r][c].t ~= "hole"
end

local function contains(board, r, c)
  return r >= 1 and r <= board.height and c >= 1 and c <= board.width
end

function M.piece_count(board)
  local n = { white = 0, black = 0, neutral = 0 }
  for _, row in ipairs(board.cells) do
    for _, cell in ipairs(row) do
      if cell.fig and cell.fig.type == "piece" then n[cell.fig.color] = n[cell.fig.color] + 1 end
    end
  end
  return n.white, n.black, n.neutral
end

-- Parser --------------------------------------------------------------------------------

local function supports(fig)
  return catalog.glyphs[figure_key(fig, "light")] ~= nil
end

local function parse_special(name, neutral, pos)
  local key = name:lower()
  local colors = specials[key]
  if name == "" or not colors then
    local known = {}
    for k in pairs(specials) do known[#known + 1] = k end
    table.sort(known)
    fen_error("unknown-special",
      string.format("unknown special '%s'; known: %s", name, table.concat(known, ", ")), pos)
  end
  local color
  local colorless = true -- box, cross
  for c in pairs(colors) do
    if c ~= "none" then colorless = false end
  end
  if neutral then
    color = "neutral"
  elseif colorless then
    color = "none"
  else
    color = name:sub(1, 1):match("%u") and "white" or "black"
  end
  if not colors[color] then
    fen_error("unsupported", string.format("special '%s' has no %s version", key, color), pos)
  end
  return { type = "special", name = key, color = color }
end

local function parse_token(body, pos)
  local mod = body:sub(1, 1)
  if mod ~= "=" and mod ~= "~" and mod ~= "!" then mod = "" end
  local rest = body:sub(#mod + 1)

  if rest:sub(1, 1) == "@" then
    if mod ~= "" and mod ~= "=" then
      fen_error("bad-token", string.format("modifier '%s' cannot apply to a special", mod), pos)
    end
    return parse_special(rest:sub(2), mod == "=", pos)
  end

  local letter = rest:sub(1, 1)
  if letter == "" or not letter:match("[KQRBNPkqrbnp]") then
    fen_error("bad-token", string.format("bad token {%s}", body), pos)
  end
  local angle_text = rest:sub(2)
  local angle = 0
  if angle_text ~= "" then
    local value = angle_text:match("^%d+$") and tonumber(angle_text)
    if not value or not ANGLES[value] then
      fen_error("bad-angle", string.format(
        "angle must be one of 0, 45, 90, 135, 180, 225, 270, 315, not '%s'", angle_text), pos)
    end
    angle = math.tointeger(value)
  end

  local color
  if mod == "=" then
    color = "neutral"
  else
    color = letter:match("%u") and "white" or "black"
  end
  local variant = ({ ["~"] = "chameleon", ["!"] = "mirror" })[mod] or "plain"
  local piece = { type = "piece", kind = letter:upper(), color = color, angle = angle,
                  variant = variant }
  if not supports(piece) then
    local v = variant == "plain" and "" or (variant .. " ")
    fen_error("unsupported", string.format("the GC fonts have no %s %s%s at %d degrees",
      color, v, PIECE_NAMES[piece.kind], angle), pos)
  end
  return piece
end

--- Parse an extended FEN. Returns a board, or raises { code = ..., message = ... }.
function M.parse(fen)
  local offset = #fen:match("^%s*")
  local text = fen:match("^%s*(%S*)")
  if text == "" then fen_error("empty", "empty FEN") end

  local rows, row = {}, {}
  local i, n = 1, #text
  while i <= n + 1 do
    local ch = i <= n and text:sub(i, i) or "/"
    local pos = offset + i - 1
    if ch == "/" then
      if #row == 0 then
        fen_error("empty-rank", string.format("rank %d is empty", #rows + 1), pos)
      end
      rows[#rows + 1] = row
      row = {}
      i = i + 1
    elseif ch:match("%d") then
      local digits = text:match("^%d+", i)
      if ch == "0" then
        fen_error("bad-count", "empty-square counts cannot start with 0", pos)
      end
      local count = tonumber(digits)
      if count > MAX_SIZE then
        fen_error("too-large", string.format("board is wider than %d files", MAX_SIZE), pos)
      end
      for _ = 1, count do row[#row + 1] = EMPTY end
      i = i + #digits
    elseif ch:match("[KQRBNPkqrbnp]") then
      row[#row + 1] = { t = "square", fig = { type = "piece", kind = ch:upper(),
        color = ch:match("%u") and "white" or "black", angle = 0, variant = "plain" } }
      i = i + 1
    elseif ch == "." then
      row[#row + 1] = { t = "hole" }
      i = i + 1
    elseif ch == "*" then
      row[#row + 1] = { t = "wall" }
      i = i + 1
    elseif ch == "{" then
      local close = text:find("}", i, true)
      if not close then fen_error("unterminated-token", "'{' without matching '}'", pos) end
      row[#row + 1] = { t = "square", fig = parse_token(text:sub(i + 1, close - 1), pos) }
      i = close + 1
    else
      fen_error("bad-char", string.format("unexpected character '%s'", ch), pos)
    end
    if #row > MAX_SIZE then
      fen_error("too-large", string.format("board is wider than %d files", MAX_SIZE),
        offset + i - 2)
    end
  end

  local width = #rows[1]
  for r, cells in ipairs(rows) do
    if #cells ~= width then
      fen_error("uneven-ranks", string.format(
        "rank %d from the top has %d squares, the first has %d", r, #cells, width))
    end
  end
  if #rows > MAX_SIZE then
    fen_error("too-large", string.format("board has more than %d ranks", MAX_SIZE))
  end
  return { cells = rows, width = width, height = #rows }
end

local function figure_token(fig)
  if fig.type == "special" then
    if fig.color == "neutral" then
      return "{=@" .. fig.name .. "}"
    end
    local name = fig.name
    if fig.color == "white" then name = name:sub(1, 1):upper() .. name:sub(2) end
    return "{@" .. name .. "}"
  end
  local letter = fig.color == "black" and fig.kind:lower() or fig.kind
  local mod = fig.color == "neutral" and "="
    or ({ plain = "", chameleon = "~", mirror = "!" })[fig.variant]
  local angle = fig.angle ~= 0 and tostring(fig.angle) or ""
  if mod == "" and angle == "" then return letter end
  return "{" .. mod .. letter .. angle .. "}"
end

--- Canonical extended FEN for a board.
function M.serialize(board)
  local ranks = {}
  for r, row in ipairs(board.cells) do
    local out, run = {}, 0
    for _, cell in ipairs(row) do
      if cell.t == "square" and not cell.fig then
        run = run + 1
      else
        if run > 0 then out[#out + 1] = tostring(run); run = 0 end
        if cell.t == "hole" then out[#out + 1] = "."
        elseif cell.t == "wall" then out[#out + 1] = "*"
        else out[#out + 1] = figure_token(cell.fig) end
      end
    end
    if run > 0 then out[#out + 1] = tostring(run) end
    ranks[r] = table.concat(out)
  end
  return table.concat(ranks, "/")
end

--- Describe each non-empty cell the way tests/vectors.json does.
function M.describe(board)
  local out = {}
  for r, row in ipairs(board.cells) do
    for c, cell in ipairs(row) do
      local d
      if cell.t == "hole" or cell.t == "wall" then
        d = cell.t
      elseif cell.fig and cell.fig.type == "piece" then
        local f = cell.fig
        d = string.format("piece:%s:%s:%d:%s", f.kind, f.color, f.angle, f.variant)
      elseif cell.fig then
        d = string.format("special:%s:%s", cell.fig.name, cell.fig.color)
      end
      if d then out[square_name(board, r, c)] = d end
    end
  end
  return out
end

-- Layout --------------------------------------------------------------------------------

local function frame_thickness(style)
  if style == "single" or style == "outline" then return SINGLE end
  if style == "double" then return DOUBLE_THIN + DOUBLE_GAP + DOUBLE_THICK end
  return 0
end

local function ring(x, y, w, h, inner, t)
  local o = inner + t
  return {
    { x - o, y - o, w + 2 * o, t },
    { x - o, y + h + inner, w + 2 * o, t },
  }, {
    { x - o, y - inner, t, h + 2 * inner },
    { x + w + inner, y - inner, t, h + 2 * inner },
  }
end

local function merge(rects, axis)
  local groups, keys = {}, {}
  for _, rc in ipairs(rects) do
    local x, y, w, h = rc[1], rc[2], rc[3], rc[4]
    local pos, thick, s, e
    if axis == 0 then pos, thick, s, e = y, h, x, x + w else pos, thick, s, e = x, w, y, y + h end
    local id = string.format("%.17g|%.17g", pos, thick)
    if not groups[id] then
      groups[id] = { pos = pos, thick = thick, spans = {} }
      keys[#keys + 1] = groups[id]
    end
    local spans = groups[id].spans
    spans[#spans + 1] = { s, e }
  end
  table.sort(keys, function(a, b)
    if a.pos ~= b.pos then return a.pos < b.pos end
    return a.thick < b.thick
  end)
  local out = {}
  for _, g in ipairs(keys) do
    table.sort(g.spans, function(a, b)
      if a[1] ~= b[1] then return a[1] < b[1] end
      return a[2] < b[2]
    end)
    local start, stop = g.spans[1][1], g.spans[1][2]
    local spans = g.spans
    spans[#spans + 1] = { math.huge, math.huge }
    for k = 2, #spans do
      local s, e = spans[k][1], spans[k][2]
      if s <= stop then
        if e > stop then stop = e end
      else
        if axis == 0 then
          out[#out + 1] = { start, g.pos, stop - start, g.thick }
        else
          out[#out + 1] = { g.pos, start, g.thick, stop - start }
        end
        start, stop = s, e
      end
    end
  end
  return out
end

local SIDES = { { "top", -1, 0 }, { "bottom", 1, 0 }, { "left", 0, -1 }, { "right", 0, 1 } }

local function border_rects(board, style, bx, by)
  if style == "none" then return {} end
  local t = SINGLE
  local horizontal, vertical = {}, {}
  local frame = style == "single" or style == "double"
  for r = 1, board.height do
    for c = 1, board.width do
      if board.cells[r][c].t ~= "hole" then
        local exposed = {}
        for _, side in ipairs(SIDES) do
          local nr, nc = r + side[2], c + side[3]
          if not is_board_square(board, nr, nc)
             and not (frame and not contains(board, nr, nc)) then
            exposed[side[1]] = true
          end
        end
        local x, y = bx + (c - 1) * U, by + (r - 1) * U
        if exposed.top then horizontal[#horizontal + 1] = { x, y - t, U, t } end
        if exposed.bottom then horizontal[#horizontal + 1] = { x, y + U, U, t } end
        if exposed.left then vertical[#vertical + 1] = { x - t, y, t, U } end
        if exposed.right then vertical[#vertical + 1] = { x + U, y, t, U } end
        for _, corner in ipairs({
          { "top", "left", x - t, y - t }, { "top", "right", x + U, y - t },
          { "bottom", "left", x - t, y + U }, { "bottom", "right", x + U, y + U },
        }) do
          if exposed[corner[1]] and exposed[corner[2]] then
            horizontal[#horizontal + 1] = { corner[3], corner[4], t, t }
          end
        end
      end
    end
  end
  local w, h = board.width * U, board.height * U
  local rings = {}
  if style == "single" then
    rings = { { 0, SINGLE } }
  elseif style == "double" then
    rings = { { 0, DOUBLE_THIN }, { DOUBLE_THIN + DOUBLE_GAP, DOUBLE_THICK } }
  end
  for _, spec in ipairs(rings) do
    local hs, vs = ring(bx, by, w, h, spec[1], spec[2])
    for _, rc in ipairs(hs) do horizontal[#horizontal + 1] = rc end
    for _, rc in ipairs(vs) do vertical[#vertical + 1] = rc end
  end
  local out = merge(horizontal, 0)
  for _, rc in ipairs(merge(vertical, 1)) do out[#out + 1] = rc end
  return out
end

local function parse_square(name, height)
  local file, rank = name:match("^([a-z])([1-9]%d?)$")
  if not file then error(string.format("bad square name '%s'", name), 0) end
  rank = tonumber(rank)
  if rank < 1 or rank > height then
    error(string.format("square '%s' is off the board", name), 0)
  end
  return height - rank + 1, FILES:find(file, 1, true)
end

local function parse_arrow(spec)
  local a, b = spec:match("^%s*([a-z]%d+)%s*[%-x>]?%s*([a-z]%d+)%s*$")
  if not a then error(string.format("bad arrow '%s'; expected e.g. 'e2-e4'", spec), 0) end
  return a, b
end

local function arrow_polygon(board, spec, bx, by)
  local a, b = parse_arrow(spec)
  local r0, c0 = parse_square(a, board.height)
  local r1, c1 = parse_square(b, board.height)
  if c0 > board.width or c1 > board.width then
    error(string.format("arrow '%s' leaves the board", spec), 0)
  end
  local ax, ay = bx + (c0 - 1 + 0.5) * U, by + (r0 - 1 + 0.5) * U
  local tx, ty = bx + (c1 - 1 + 0.5) * U, by + (r1 - 1 + 0.5) * U
  local dx, dy = tx - ax, ty - ay
  local length = math.sqrt(dx * dx + dy * dy)
  if length == 0 then
    error(string.format("arrow '%s' starts and ends on the same square", spec), 0)
  end
  local ux, uy = dx / length, dy / length
  local nx, ny = -uy, ux
  local head = math.min(ARROW_HEAD_LENGTH, 0.6 * length)
  local hx, hy = tx - ux * head, ty - uy * head
  local s, w = ARROW_SHAFT / 2, ARROW_HEAD_WIDTH / 2
  return {
    { ax + nx * s, ay + ny * s },
    { hx + nx * s, hy + ny * s },
    { hx + nx * w, hy + ny * w },
    { tx, ty },
    { hx - nx * w, hy - ny * w },
    { hx - nx * s, hy - ny * s },
    { ax - nx * s, ay - ny * s },
  }
end

local WALL_FILL = "666666" -- a solid wall's interior: 40% gray, outlined in black

--- Black lines inside solid walls where they meet a square (see geometry.py).
local function wall_outline_rects(board, style, bx, by)
  local function outlines(r, c)
    local cell = contains(board, r, c) and board.cells[r][c] or nil
    return (cell ~= nil and cell.t == "square")
      or (style == "none" and not (cell ~= nil and cell.t == "wall"))
  end
  local t = SINGLE
  local horizontal, vertical = {}, {}
  for r = 1, board.height do
    for c = 1, board.width do
      if board.cells[r][c].t == "wall" then
        local edge = {}
        for _, side in ipairs(SIDES) do edge[side[1]] = outlines(r + side[2], c + side[3]) end
        local x, y = bx + (c - 1) * U, by + (r - 1) * U
        if edge.top then horizontal[#horizontal + 1] = { x, y, U, t } end
        if edge.bottom then horizontal[#horizontal + 1] = { x, y + U - t, U, t } end
        if edge.left then vertical[#vertical + 1] = { x, y, t, U } end
        if edge.right then vertical[#vertical + 1] = { x + U - t, y, t, U } end
        for _, corner in ipairs({
          { "top", "left", -1, -1, x, y }, { "top", "right", -1, 1, x + U - t, y },
          { "bottom", "left", 1, -1, x, y + U - t }, { "bottom", "right", 1, 1, x + U - t, y + U - t },
        }) do
          if not edge[corner[1]] and not edge[corner[2]] and outlines(r + corner[3], c + corner[4]) then
            horizontal[#horizontal + 1] = { corner[5], corner[6], t, t }
          end
        end
      end
    end
  end
  local out = merge(horizontal, 0)
  for _, rc in ipairs(merge(vertical, 1)) do out[#out + 1] = rc end
  return out
end

--- Layout in font units (y down), without caption or padding.
function M.layout(board, opts)
  local t = frame_thickness(opts.border)
  local lay = {
    width = board.width * U + 2 * t,
    height = board.height * U + 2 * t,
    board_x = t,
    board_y = t,
    rects = {},
    wall_fills = {},
    arrows = {},
  }
  for r = 1, board.height do
    for c = 1, board.width do
      if board.cells[r][c].t == "wall" and opts.wall ~= "box" then
        lay.wall_fills[#lay.wall_fills + 1] = { t + (c - 1) * U, t + (r - 1) * U, U, U }
      end
    end
  end
  for _, rc in ipairs(border_rects(board, opts.border, t, t)) do lay.rects[#lay.rects + 1] = rc end
  if opts.wall ~= "box" then
    for _, rc in ipairs(wall_outline_rects(board, opts.border, t, t)) do
      lay.rects[#lay.rects + 1] = rc
    end
  end
  for _, spec in ipairs(opts.arrows or {}) do
    lay.arrows[#lay.arrows + 1] = arrow_polygon(board, spec, t, t)
  end
  return lay
end

-- TeX emission --------------------------------------------------------------------------

--- Font units as a decimal number of squares: 100 -> ".05", -233 -> "-.1165".
local function num(units)
  local s = string.format("%.5f", units / U):gsub("0+$", ""):gsub("%.$", "")
  if s == "" or s == "-0" then return "0" end
  if s:sub(1, 2) == "0." then return s:sub(2) end
  if s:sub(1, 3) == "-0." then return "-" .. s:sub(3) end
  return s
end
M.num = num

local function cell_glyph(board, r, c, opts)
  local cell = board.cells[r][c]
  local sh = shade(board, r, c)
  local key
  if cell.t == "square" and cell.fig then
    key = figure_key(cell.fig, sh)
  elseif cell.t == "square" then
    key = "square:" .. sh
  elseif cell.t == "wall" and opts.wall == "box" then
    key = "special:box:none:" .. sh
  else
    key = "square:light" -- blank glyph: advances one square
  end
  return catalog.glyphs[key]
end

local function rank_runs(board, r, opts)
  local runs = {}
  for c = 1, board.width do
    local g = cell_glyph(board, r, c, opts)
    local font, code, dx = g[1], g[2], g[3]
    local text = utf8.char(code)
    if dx then text = "\\gcfix{" .. num(dx) .. "}{" .. text .. "}" end
    if #runs > 0 and runs[#runs][1] == font then
      runs[#runs][2] = runs[#runs][2] .. text
    else
      runs[#runs + 1] = { font, text }
    end
  end
  local out = {}
  for _, run in ipairs(runs) do out[#out + 1] = "\\gc" .. run[1] .. "{" .. run[2] .. "}" end
  return table.concat(out)
end

--- Returns width, height, body lines (a list) and the piece count string.
function M.tex_parts(board, opts)
  local lay = M.layout(board, opts)
  local height = lay.height
  local lines = {}
  for r = 1, board.height do
    local baseline = height - (lay.board_y + (r - 1) * U + BASELINE)
    lines[#lines + 1] = string.format("\\gcrank{%s}{%s}{%s}",
      num(lay.board_x), num(baseline), rank_runs(board, r, opts))
  end
  local function rects(list)
    local parts = {}
    for _, rc in ipairs(list) do
      local x, y, w, h = rc[1], rc[2], rc[3], rc[4]
      parts[#parts + 1] = string.format("\\gcr{%s}{%s}{%s}{%s}",
        num(x), num(height - y - h), num(w), num(h))
    end
    return table.concat(parts)
  end
  if #lay.wall_fills > 0 then
    lines[#lines + 1] = "\\gcfills{" .. WALL_FILL .. "}{" .. rects(lay.wall_fills) .. "}"
  end
  if #lay.rects > 0 then
    lines[#lines + 1] = "\\gcrects{" .. rects(lay.rects) .. "}"
  end
  if #lay.arrows > 0 then
    local parts = {}
    for _, pts in ipairs(lay.arrows) do
      parts[#parts + 1] = string.format("\\gcm{%s}{%s}", num(pts[1][1]), num(height - pts[1][2]))
      for k = 2, #pts do
        parts[#parts + 1] = string.format("\\gcl{%s}{%s}", num(pts[k][1]), num(height - pts[k][2]))
      end
      parts[#parts + 1] = "\\gcz"
    end
    lines[#lines + 1] = string.format("\\gcarrows{%s}{%s}{%s}",
      (opts.arrow_color or "000000"):upper(), string.format("%g", opts.arrow_opacity or 0.6),
      table.concat(parts))
  end
  local count = ""
  if opts.count then
    local w, b, n = M.piece_count(board)
    count = n > 0 and string.format("(%d+%d+%d)", w, b, n) or string.format("(%d+%d)", w, b)
  end
  return num(lay.width), num(height), lines, count
end

-- TeX interface -------------------------------------------------------------------------

local function split_arrows(s)
  local out = {}
  for item in (s or ""):gmatch("[^,]+") do
    if item:match("%S") then out[#out + 1] = item end
  end
  return out
end

--- Called by \gcdiagram: typesets \gcLuaResult{width}{height}{body}{count}.
function M.typeset(fen, border, wall, arrows, count, arrow_color, arrow_opacity)
  local ok, result = pcall(function()
    local board = M.parse(fen)
    local opts = {
      border = border, wall = wall, arrows = split_arrows(arrows), count = count,
      arrow_color = arrow_color, arrow_opacity = tonumber(arrow_opacity),
    }
    local w, h, lines, cnt = M.tex_parts(board, opts)
    return string.format("\\gcLuaResult{%s}{%s}{%s}{%s}", w, h, table.concat(lines), cnt)
  end)
  if ok then
    tex.sprint(result)
  else
    local message = type(result) == "table" and result.message or tostring(result)
    tex.error("gcdiagram: " .. message .. " in FEN '" .. fen .. "'")
  end
end

return M
