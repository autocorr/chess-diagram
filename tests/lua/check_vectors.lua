-- texlua tests/lua/check_vectors.lua <vectors.lua>
-- Runs the shared FEN conformance vectors (converted to a Lua table by tests/test_latex.py)
-- against latex/gcdiagram.lua. Prints one line per failure; exits non-zero on failure.

local gc = require("gcdiagram")
local vectors = dofile(arg[1])
local failures = 0

local function fail(fen, msg)
  failures = failures + 1
  print(string.format("FAIL %q: %s", fen, msg))
end

local function same(a, b)
  for k, v in pairs(a) do if b[k] ~= v then return false end end
  for k, v in pairs(b) do if a[k] ~= v then return false end end
  return true
end

for _, case in ipairs(vectors.valid) do
  local ok, board = pcall(gc.parse, case.fen)
  if not ok then
    fail(case.fen, "unexpected error " .. (board.code or tostring(board)))
  else
    if board.width ~= case.width or board.height ~= case.height then
      fail(case.fen, string.format("size %dx%d", board.width, board.height))
    end
    if not same(gc.describe(board), case.cells) then fail(case.fen, "cells differ") end
    local canonical = gc.serialize(board)
    if canonical ~= case.canonical then fail(case.fen, "canonical " .. canonical) end
    if gc.serialize(gc.parse(canonical)) ~= canonical then fail(case.fen, "not stable") end
  end
end

for _, case in ipairs(vectors.invalid) do
  local ok, err = pcall(gc.parse, case.fen)
  if ok then
    fail(case.fen, "parsed but expected " .. case.error)
  elseif type(err) ~= "table" or err.code ~= case.error then
    fail(case.fen, "got " .. (type(err) == "table" and err.code or tostring(err))
      .. ", expected " .. case.error)
  end
end

print(string.format("%d valid, %d invalid, %d failures",
  #vectors.valid, #vectors.invalid, failures))
os.exit(failures == 0 and 0 or 1)
