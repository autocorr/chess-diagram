-- texlua tests/lua/emit.lua <cases.lua>
-- Prints the \gcbox parts that latex/gcdiagram.lua computes for each case, in the
-- format tests/test_latex.py compares against the Python renderer:
--   ==<name>\n<width>\n<height>\n<count>\n<body lines...>

local gc = require("gcdiagram")
local cases = dofile(arg[1])

for _, case in ipairs(cases) do
  local board = gc.parse(case.fen)
  local w, h, lines, count = gc.tex_parts(board, case.opts)
  io.write("==", case.name, "\n", w, "\n", h, "\n", count, "\n")
  for _, line in ipairs(lines) do io.write(line, "\n") end
end
