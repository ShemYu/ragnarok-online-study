-- ASCII canonical records. Strings become raw-byte hex, including Unicode/NUL.
-- Key types stay distinct; finite doubles use round-trippable 17-digit text.
-- Tables are expanded by value. Cycles, metatables and unsupported types fail.
local type_, next_, getmetatable_ = type, next, getmetatable
local format_, byte_, concat_, sort_ = string.format, string.byte, table.concat, table.sort
local huge = math.huge
local function hex(s)
  local out = {}
  for i = 1, #s do out[i] = format_('%02x', byte_(s, i)) end
  return concat_(out)
end
local function number(n, key)
  if n ~= n or n == huge or n == -huge then error('nonfinite number') end
  if n == 0 then
    if not key and 1 / n == -huge then return 'n-0;' end
    return 'n0;'
  end
  return 'n' .. format_('%.17g', n) .. ';'
end
local function keytoken(k, counts)
  local t = type_(k)
  if t == 'string' then counts.stringKeys = counts.stringKeys + 1; return 's' .. hex(k) .. ';' end
  if t == 'number' then counts.numberKeys = counts.numberKeys + 1; return number(k, true) end
  if t == 'boolean' then counts.booleanKeys = counts.booleanKeys + 1; return k and 'b1;' or 'b0;' end
  error('unsupported table key type: ' .. t)
end
local function entries(t, counts)
  if getmetatable_(t) ~= nil then error('metatable is not supported') end
  local out = {}
  for k, v in next_, t do out[#out + 1] = { keytoken(k, counts), v } end
  sort_(out, function(a, b) return a[1] < b[1] end)
  counts.tables = counts.tables + 1
  counts.entries = counts.entries + #out
  return out
end
local encode
encode = function(value, active, counts, depth)
  if depth > 256 then error('table nesting exceeds 256') end
  local t = type_(value)
  if t == 'nil' then counts.nilValues = counts.nilValues + 1; return 'z;' end
  if t == 'boolean' then counts.booleanValues = counts.booleanValues + 1; return value and 'b1;' or 'b0;' end
  if t == 'number' then counts.numberValues = counts.numberValues + 1; return number(value, false) end
  if t == 'string' then
    counts.stringValues = counts.stringValues + 1
    counts.stringBytes = counts.stringBytes + #value
    return 's' .. hex(value) .. ';'
  end
  if t ~= 'table' then error('unsupported value type: ' .. t) end
  if active[value] then error('cycle in tbl') end
  active[value] = true
  local list = entries(value, counts)
  local out = {'t', tostring(#list), '{'}
  for _, pair in ipairs(list) do
    out[#out + 1] = pair[1]
    out[#out + 1] = encode(pair[2], active, counts, depth + 1)
  end
  out[#out + 1] = '}'
  active[value] = nil
  return concat_(out)
end
function __roundtrip_canonical(root)
  if type_(root) ~= 'table' then error('tbl is not a table') end
  local counts = {tables=0, entries=0, stringKeys=0, numberKeys=0, booleanKeys=0,
                  stringValues=0, numberValues=0, booleanValues=0, nilValues=0, stringBytes=0}
  local list = entries(root, counts)
  local active, lines = {[root]=true}, {}
  for _, pair in ipairs(list) do
    lines[#lines + 1] = pair[1] .. '\t' .. encode(pair[2], active, counts, 1)
  end
  local names = {'tables','entries','stringKeys','numberKeys','booleanKeys','stringValues',
                 'numberValues','booleanValues','nilValues','stringBytes'}
  local metrics = {'rootEntries=' .. tostring(#list)}
  for _, name in ipairs(names) do metrics[#metrics + 1] = name .. '=' .. tostring(counts[name]) end
  -- Every canonical line is ASCII and contains no NUL; the bridge is NUL-terminated.
  return concat_(metrics, ',') .. '\n' .. concat_(lines, '\n')
end
