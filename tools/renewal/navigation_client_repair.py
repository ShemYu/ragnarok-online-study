#!/usr/bin/env python3
"""Generate the repaired navigation bundle and Taiwan request aliases (T05.007).

    python3 -I -B tools/renewal/navigation_client_repair.py \
        BUNDLE_SOURCE TAIWAN_TABLE_DIR OUTPUT

BUNDLE_SOURCE is the exact patched Ragnarok Offline 1.6.3 Online.js and
TAIWAN_TABLE_DIR the directory holding the six exact navi_<role>_tw.lub
chunks. Arguments only locate those bytes: every pin, the loader window, the
six requests and the mod metadata are fixed below and cannot be overridden.
OUTPUT is a new private evidence envelope:

    OUTPUT/Online.js                   the repaired bundle (not a mod)
    OUTPUT/tw-navigation-request-compat/  the seven-file alias mod: mod.json and
        data/luafiles514/lua files/navigation/navi_<role>_krpri.lub
    OUTPUT/repair-manifest.json, OUTPUT/COMPLETE.json (written last)

Only the original loadLuaValue function, bytes [10727952, 10731097), changes.
The six exact path/global requests get a raw-byte transport inside it; every
other table keeps the original conversion byte for byte. The stock chunks are
streamed, hashed and copied as opaque bytes; they are never decoded or parsed.
Every output is read back before completion. On failure only the entries this
run created are removed. Standard library only (Python 3.9). See
NAVIGATION_CLIENT_REPAIR.md.
"""

import hashlib
import json
import os
import stat
import sys

TASK = "T05.007"

# The frozen normative profile.json, verbatim (4838 bytes; checked at import).
PROFILE_SHA256 = "70508ac9f0b5d01cdee31c2f150f8a8f80e87bd6bf83b102394165d59032265b"
PROFILE_TEXT = r'''{
  "client_commit": "775f8847a8b09749d03c82fcb554e155401d1e02",
  "entry_extraction": {
    "end_byte_exclusive": 10751357,
    "sha256": "21ef7752cbd05bdabd5e4aadd2defbf4cef776340d6444221a9c04b3eb235d7a",
    "start_byte": 10750323
  },
  "inputs": [
    {
      "bytes": 13166284,
      "file": "Online.js",
      "role": "bundle",
      "sha256": "80f4371cc8da2bb54432e46e7e34dfaf7acc56444b28c6fbc6a99c6ba22933ea"
    },
    {
      "bytes": 67328,
      "file": "navi_map_tw.lub",
      "role": "map",
      "sha256": "e7c8d566b5883df68d01830f0ce4ec385fc8ac084a1a8f6944bd517d89a046dc"
    },
    {
      "bytes": 396243,
      "file": "navi_mob_tw.lub",
      "role": "mob",
      "sha256": "02aeb90a6df4af8f2e4fc8adf5a88f70b5ac1c48e32373a7cba57439a776c3c7"
    },
    {
      "bytes": 1025994,
      "file": "navi_npc_tw.lub",
      "role": "npc",
      "sha256": "7b760b652d8ce5a6353811aa57d433848b056f6bdc99a3ddbb585f88bb44b528"
    },
    {
      "bytes": 594363,
      "file": "navi_link_tw.lub",
      "role": "link",
      "sha256": "f6526637f8cfc8755b92fad9e496f7c97439715db34a6efd430dfb870b62ff10"
    },
    {
      "bytes": 1556072,
      "file": "navi_linkdistance_tw.lub",
      "role": "linkdistance",
      "sha256": "26cea879a399a1362a02deecf0ef3b07c7d4bfcdf01938f08f98338e5f05c193"
    },
    {
      "bytes": 3840599,
      "file": "navi_npcdistance_tw.lub",
      "role": "npcdistance",
      "sha256": "3e896b2ba29de46f40ab36e43917359b376612ef00b3b4c0e2eb0cc81cb95471"
    }
  ],
  "loader_extraction": {
    "end_byte_exclusive": 10731097,
    "sha256": "402018cbf968171f3a939e00c0067101496d0d19f519e28ab342176223623554",
    "start_byte": 10724820
  },
  "mod_json": {
    "bytes": 278,
    "sha256": "f207ec962995a4f9d5bc09b71d93ecea8528ca44ed90ec359c6188c86471c336"
  },
  "package": {
    "author": "Project local integration",
    "default": "off",
    "description": "臺灣導航資料請求相容檔；保留原始資料位元組。",
    "name": "tw-navigation-request-compat",
    "requires": {
      "app": "=1.6.3",
      "era": "renewal"
    },
    "version": "1.0.0"
  },
  "profile": "tw-navigation-repair-v1",
  "qualified_baseline": {
    "expanded_value_nodes": 694399,
    "number_occurrences": 357862,
    "stock_root_rows": {
      "link": 4515,
      "linkdistance": 1938,
      "map": 764,
      "mob": 3541,
      "npc": 9939,
      "npcdistance": 1599
    },
    "string_occurrences": 181674,
    "unequal_string_occurrences": 88
  },
  "queue_extraction": {
    "end_byte_exclusive": 10639142,
    "sha256": "74a722c47f51211be7b94634c5daa0c55d04ad68f55f93544bceab9898efc662",
    "start_byte": 10638881
  },
  "requests": [
    {
      "global": "Navi_Map",
      "path": "data/luafiles514/lua files/navigation/navi_map_krpri.lub",
      "role": "map",
      "target": "tw-navigation-request-compat/data/luafiles514/lua files/navigation/navi_map_krpri.lub"
    },
    {
      "global": "Navi_Mob",
      "path": "data/luafiles514/lua files/navigation/navi_mob_krpri.lub",
      "role": "mob",
      "target": "tw-navigation-request-compat/data/luafiles514/lua files/navigation/navi_mob_krpri.lub"
    },
    {
      "global": "Navi_Npc",
      "path": "data/luafiles514/lua files/navigation/navi_npc_krpri.lub",
      "role": "npc",
      "target": "tw-navigation-request-compat/data/luafiles514/lua files/navigation/navi_npc_krpri.lub"
    },
    {
      "global": "Navi_Link",
      "path": "data/luafiles514/lua files/navigation/navi_link_krpri.lub",
      "role": "link",
      "target": "tw-navigation-request-compat/data/luafiles514/lua files/navigation/navi_link_krpri.lub"
    },
    {
      "global": "Navi_Distance",
      "path": "data/luafiles514/lua files/navigation/navi_linkdistance_krpri.lub",
      "role": "linkdistance",
      "target": "tw-navigation-request-compat/data/luafiles514/lua files/navigation/navi_linkdistance_krpri.lub"
    },
    {
      "global": "Navi_NpcDistance",
      "path": "data/luafiles514/lua files/navigation/navi_npcdistance_krpri.lub",
      "role": "npcdistance",
      "target": "tw-navigation-request-compat/data/luafiles514/lua files/navigation/navi_npcdistance_krpri.lub"
    }
  ],
  "schema": 1,
  "source_base": "612762c69159de3ca85e6e13190dd4aafea33fd5",
  "task": "T05.007",
  "upstream_commit": "2c3b2612973fb8d0ae6ad366a2b298686f2404cb",
  "window": {
    "end_byte_exclusive": 10731097,
    "end_marker": "\n/**\n* Loads System/mapInfo.lub",
    "prefix_sha256": "066ab84b1627bb7a7f9305d11782ed7dc0ac6c26482ac95748724712f5dc827b",
    "sha256": "ea24a0af0deeec11b75f14c5865813609ffd6625de06d7391ba5f8a89f80b664",
    "start_byte": 10727952,
    "start_marker": "function loadLuaValue(file_path, variable_name, callback, onEnd) {",
    "suffix_sha256": "3bda8df80ece94adc5087ac0de5e24aa2603698ea2f8676a7a864fb7dec9e225"
  }
}
'''

BUNDLE_CAP = 32 << 20        # Online.js is read whole, under this bound
SMALL_CAP = 1 << 20          # the generator's own source
CHUNK = 1 << 20              # alias streaming read size
BUNDLE_OUT = "Online.js"
MANIFEST = "repair-manifest.json"
COMPLETE = "COMPLETE.json"
COMPLETE_PARTIAL = ".COMPLETE.json.partial"
DIR_MODE = 0o700
FILE_MODE = 0o600

_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class RepairError(Exception):
    """A refusal or failure with a bounded, path-free diagnosis."""


def canonical(value):
    """The one JSON serialization used for every file this tool writes."""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _why(error):
    """OS error reason without the path the exception may carry."""
    return error.strerror or type(error).__name__


def _load_profile():
    data = PROFILE_TEXT.encode("utf-8")
    if _sha(data) != PROFILE_SHA256:
        raise RuntimeError("embedded profile differs from the frozen profile.json")
    profile = json.loads(data)
    if canonical(profile) != data:
        raise RuntimeError("embedded profile is not canonical")
    return profile


PROFILE = _load_profile()


# ---------------------------------------------------------------- the repair

# Inserted after the function's opening line. Local to loadLuaValue: it uses
# only lua, userStringDecoder, userCharpage, navigationServerLinks and
# navigationNameSwap, which the original function already reaches, plus
# language intrinsics. The Lua chunk has no backslash or backtick, so the
# plain template literal passes it through unchanged.
NAVIGATION_HELPERS = """\t// T05.007: the six navigation tables leave Lua with every string, key or
\t// value, spelled as the hex of its raw bytes, and each one is decoded on its
\t// own with the user's charset. Decoding the whole JSON text at once let a
\t// Big5 lead byte take the backslash of an escape as its trail byte, so the
\t// character b3 5c arrived followed by a literal "u005c". Every other file
\t// keeps the conversion below.
\tconst navigationRequests = {
@@REQUESTS@@
\t};
\tconst navigationTransport = Object.prototype.hasOwnProperty.call(navigationRequests, variable_name) && navigationRequests[variable_name] === file_path;
\t// Arrays are tables keyed exactly 1..n, as before; any other table is an
\t// object keyed "s" + hex (a string) or "n" + digits (an integer key under
\t// 1e13). Anything else -- boolean or other numeric keys, keys that meet once
\t// decoded, cycles, metatables, non-finite numbers, other value types or a
\t// missing global -- is an error, never a substitute table. Lua reports it
\t// through the same callback (a leading "!"), so no Lua error is left on the
\t// shared state's stack; it is thrown here, into the usual catch below.
\tfunction navigationValue(ctx) {
\t\tlet text = null;
\t\tctx.extractValue = (value) => {
\t\t\ttext = null;
\t\t\tif (!(value instanceof Uint8Array)) return;
\t\t\tconst parts = [];
\t\t\tfor (let i = 0; i < value.length; i += 8192) {
\t\t\t\tconst chunk = value.subarray(i, i + 8192);
\t\t\t\tfor (let j = 0; j < chunk.length; j++) if (chunk[j] < 32 || chunk[j] > 126) return;
\t\t\t\tparts.push(String.fromCharCode.apply(null, chunk));
\t\t\t}
\t\t\ttext = parts.join("");
\t\t};
\t\tlua.doStringSync(`
\t\t\t\t\t\t\tlocal hex, format, concat, huge = {}, string.format, table.concat, math.huge
\t\t\t\t\t\t\tfor i = 0, 255 do hex[string.char(i)] = format("%02x", i) end
\t\t\t\t\t\t\tlocal function fail(what) error("navigation conversion: " .. what, 0) end
\t\t\t\t\t\t\tlocal function key_text(k)
\t\t\t\t\t\t\t\tif type(k) == "string" then return "s" .. (k:gsub(".", hex)) end
\t\t\t\t\t\t\t\tif type(k) == "number" and k % 1 == 0 and k > -1e13 and k < 1e13 then
\t\t\t\t\t\t\t\t\tif k == 0 then return "n0" end
\t\t\t\t\t\t\t\t\treturn "n" .. format("%.0f", k)
\t\t\t\t\t\t\t\tend
\t\t\t\t\t\t\t\tfail("unsupported " .. type(k) .. " key")
\t\t\t\t\t\t\tend
\t\t\t\t\t\t\tlocal active = {}
\t\t\t\t\t\t\tlocal encode
\t\t\t\t\t\t\tencode = function(value, depth)
\t\t\t\t\t\t\t\tlocal kind = type(value)
\t\t\t\t\t\t\t\tif kind == "string" then return '"' .. (value:gsub(".", hex)) .. '"' end
\t\t\t\t\t\t\t\tif kind == "number" then
\t\t\t\t\t\t\t\t\tif value ~= value or value == huge or value == -huge then fail("non-finite number") end
\t\t\t\t\t\t\t\t\treturn format("%.17g", value)
\t\t\t\t\t\t\t\tend
\t\t\t\t\t\t\t\tif kind == "boolean" then return value and "true" or "false" end
\t\t\t\t\t\t\t\tif kind ~= "table" then fail("unsupported " .. kind .. " value") end
\t\t\t\t\t\t\t\tif active[value] then fail("cycle") end
\t\t\t\t\t\t\t\tif depth > 256 then fail("nesting deeper than 256") end
\t\t\t\t\t\t\t\tif getmetatable(value) ~= nil then fail("table with a metatable") end
\t\t\t\t\t\t\t\tactive[value] = true
\t\t\t\t\t\t\t\tlocal count, highest, dense = 0, 0, true
\t\t\t\t\t\t\t\tfor k in next, value do
\t\t\t\t\t\t\t\t\tcount = count + 1
\t\t\t\t\t\t\t\t\tif type(k) ~= "number" or k < 1 or k % 1 ~= 0 then dense = false
\t\t\t\t\t\t\t\t\telseif k > highest then highest = k end
\t\t\t\t\t\t\t\tend
\t\t\t\t\t\t\t\tlocal out, text = {}
\t\t\t\t\t\t\t\tif dense and count == highest then
\t\t\t\t\t\t\t\t\tfor i = 1, count do out[i] = encode(rawget(value, i), depth + 1) end
\t\t\t\t\t\t\t\t\ttext = "[" .. concat(out, ",") .. "]"
\t\t\t\t\t\t\t\telse
\t\t\t\t\t\t\t\t\tlocal n = 0
\t\t\t\t\t\t\t\t\tfor k, v in next, value do
\t\t\t\t\t\t\t\t\t\tn = n + 1
\t\t\t\t\t\t\t\t\t\tout[n] = '"' .. key_text(k) .. '":' .. encode(v, depth + 1)
\t\t\t\t\t\t\t\t\tend
\t\t\t\t\t\t\t\t\ttext = "{" .. concat(out, ",") .. "}"
\t\t\t\t\t\t\t\tend
\t\t\t\t\t\t\t\tactive[value] = nil
\t\t\t\t\t\t\t\treturn text
\t\t\t\t\t\t\tend
\t\t\t\t\t\t\t${navigationServerLinks(variable_name)}${navigationNameSwap(variable_name)}
\t\t\t\t\t\t\tlocal ok, result = pcall(function()
\t\t\t\t\t\t\t\tif type(${variable_name}) ~= "table" then fail("${variable_name} is not a table") end
\t\t\t\t\t\t\t\treturn encode(${variable_name}, 1)
\t\t\t\t\t\t\tend)
\t\t\t\t\t\t\tif ok then extractValue(result) else extractValue("!" .. tostring(result)) end
\t\t\t\t\t\t`);
\t\t// Released here: the callback stays registered in Lua until the next load.
\t\tconst json = text;
\t\ttext = null;
\t\tif (json === null) throw new Error(variable_name + ": the navigation value did not leave Lua as ASCII");
\t\tif (json.charAt(0) === "!") throw new Error(variable_name + ": " + json.slice(1));
\t\tconst decoded = new Map();
\t\tconst decodeHex = (hex) => {
\t\t\tlet value = decoded.get(hex);
\t\t\tif (value !== undefined) return value;
\t\t\tif (hex.length % 2 !== 0 || !/^[0-9a-f]*$/.test(hex)) throw new Error(variable_name + ": malformed navigation string");
\t\t\tconst bytes = new Uint8Array(hex.length / 2);
\t\t\tfor (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
\t\t\tvalue = userStringDecoder.decode(bytes, userCharpage);
\t\t\tif (typeof value !== "string" || (value === "" && bytes.length > 0)) throw new Error(variable_name + ": a navigation string could not be decoded");
\t\t\tdecoded.set(hex, value);
\t\t\treturn value;
\t\t};
\t\tconst rebuild = (node) => {
\t\t\tif (typeof node === "string") return decodeHex(node);
\t\t\tif (typeof node === "number" || typeof node === "boolean") return node;
\t\t\tif (Array.isArray(node)) {
\t\t\t\tfor (let i = 0; i < node.length; i++) node[i] = rebuild(node[i]);
\t\t\t\treturn node;
\t\t\t}
\t\t\tif (node === null || typeof node !== "object") throw new Error(variable_name + ": unexpected navigation value");
\t\t\tconst table = {};
\t\t\tfor (const key of Object.keys(node)) {
\t\t\t\tlet name;
\t\t\t\tif (key.charAt(0) === "s") name = decodeHex(key.slice(1));
\t\t\t\telse if (/^n(?:0|-?[1-9][0-9]*)$/.test(key)) name = key.slice(1);
\t\t\t\telse throw new Error(variable_name + ": unsupported navigation key");
\t\t\t\tif (Object.prototype.hasOwnProperty.call(table, name)) throw new Error(variable_name + ": navigation keys collide once decoded");
\t\t\t\tObject.defineProperty(table, name, { value: rebuild(node[key]), writable: true, enumerable: true, configurable: true });
\t\t\t}
\t\t\treturn table;
\t\t};
\t\treturn rebuild(JSON.parse(json));
\t}
"""

# The original conversion, unchanged, becomes the else branch.
BRANCH_OPEN_AT = b"\t\t\t\tctx.extractValue = (value) => {\n"
BRANCH_OPEN = b"\t\t\t\tif (navigationTransport) result = navigationValue(ctx);\n\t\t\t\telse {\n"
BRANCH_CLOSE_AT = b"\t\t\t\tlua.unmountFile(file_path);\n\t\t\t\tcallback.call(null, result);\n"
BRANCH_CLOSE = b"\t\t\t\t}\n"


def navigation_helpers(profile):
    lines = []
    requests = profile["requests"]
    for index, request in enumerate(requests):
        comma = "," if index + 1 < len(requests) else ""
        lines.append("\t\t" + json.dumps(request["global"]) + ": " + json.dumps(request["path"]) + comma)
    text = NAVIGATION_HELPERS.replace("@@REQUESTS@@", "\n".join(lines))
    return text.encode("utf-8")


def _unique(data, needle, what):
    first = data.find(needle)
    if first < 0 or data.find(needle, first + 1) >= 0:
        raise RepairError(f"bundle: {what} is not a unique delimiter")
    return first


def repair_window(window, profile):
    """The replacement for the original loadLuaValue window."""
    start = profile["window"]["start_marker"].encode("utf-8") + b"\n"
    if not window.startswith(start) or window.count(start) != 1:
        raise RepairError("bundle: window does not begin with the loadLuaValue signature")
    opening = _unique(window, BRANCH_OPEN_AT, "the conversion callback")
    closing = _unique(window, BRANCH_CLOSE_AT, "the unmount/callback pair")
    if not len(start) < opening < closing:
        raise RepairError("bundle: window anchors are out of order")
    return b"".join([
        window[:len(start)], navigation_helpers(profile),
        window[len(start):opening], BRANCH_OPEN,
        window[opening:closing], BRANCH_CLOSE,
        window[closing:],
    ])


def _region(data, spec, offset=0):
    return data[spec["start_byte"] + offset:spec["end_byte_exclusive"] + offset]


def repair_bundle(bundle, profile):
    """Check the pinned bundle's delimiters/regions and return the repaired bytes."""
    win = profile["window"]
    start, end = win["start_byte"], win["end_byte_exclusive"]
    if _sha(bundle) != profile["inputs"][0]["sha256"] or len(bundle) != profile["inputs"][0]["bytes"]:
        raise RepairError("bundle: identity differs from the pin")
    if _unique(bundle, win["start_marker"].encode("utf-8"), "the loadLuaValue signature") != start:
        raise RepairError("bundle: loadLuaValue is not at the pinned offset")
    if _unique(bundle, win["end_marker"].encode("utf-8"), "the mapInfo comment") != end:
        raise RepairError("bundle: the mapInfo comment is not at the pinned offset")
    window, prefix, suffix = bundle[start:end], bundle[:start], bundle[end:]
    if (_sha(window), _sha(prefix), _sha(suffix)) != (win["sha256"], win["prefix_sha256"], win["suffix_sha256"]):
        raise RepairError("bundle: window, prefix or suffix differs from the pin")
    for name in ("queue_extraction", "loader_extraction", "entry_extraction"):
        if _sha(_region(bundle, profile[name])) != profile[name]["sha256"]:
            raise RepairError(f"bundle: {name} region differs from the pin")
    new_window = repair_window(window, profile)
    try:
        new_window.decode("utf-8")
    except UnicodeDecodeError:
        raise RepairError("bundle: repaired window is not UTF-8") from None
    repaired = prefix + new_window + suffix
    shift = len(new_window) - len(window)
    # Independent re-checks on the result: unchanged prefix/suffix, the
    # separately bound regions where they now lie, unique delimiters.
    checks = (
        _sha(repaired[:start]) == win["prefix_sha256"],
        _sha(repaired[start + len(new_window):]) == win["suffix_sha256"],
        _sha(_region(repaired, profile["queue_extraction"])) == profile["queue_extraction"]["sha256"],
        _sha(_region(repaired, profile["entry_extraction"], shift)) == profile["entry_extraction"]["sha256"],
        repaired[profile["loader_extraction"]["start_byte"]:start]
        == bundle[profile["loader_extraction"]["start_byte"]:start],
        repaired.count(win["start_marker"].encode("utf-8")) == 1,
        repaired.find(win["end_marker"].encode("utf-8")) == start + len(new_window),
        repaired.count(win["end_marker"].encode("utf-8")) == 1,
    )
    if not all(checks):
        raise RepairError("bundle: repaired result failed an unchanged-region check")
    return repaired


# ---------------------------------------------------------------- paths


def _components(path, what):
    """Absolute path of an ordinary argument, refusing dot/dot-dot/empty parts."""
    if not isinstance(path, str) or not path:
        raise RepairError(f"{what}: empty path")
    if "\0" in path:
        raise RepairError(f"{what}: path contains NUL")
    parts = path.split("/")
    if path.startswith("/"):
        parts = parts[1:]
        base = "/"
    else:
        base = os.getcwd()
    for part in parts:
        if part in ("", ".", ".."):
            raise RepairError(f"{what}: path has an empty, '.' or '..' component")
    return os.path.join(base, *parts)


def _no_symlink_ancestors(absolute, what, include_last):
    """lstat every prefix; refuse a symlink or a non-directory ancestor."""
    parts = absolute.split("/")[1:]
    current = "/"
    last = len(parts) - 1
    for index, part in enumerate(parts):
        current = os.path.join(current, part)
        if index == last and not include_last:
            break
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            raise RepairError(f"{what}: a path component does not exist") from None
        except OSError as error:
            raise RepairError(f"{what}: cannot inspect path ({_why(error)})") from None
        if stat.S_ISLNK(st.st_mode):
            raise RepairError(f"{what}: path has a symbolic link component")
        if index < last and not stat.S_ISDIR(st.st_mode):
            raise RepairError(f"{what}: an ancestor is not a directory")


def _resolve_source(path, what):
    absolute = _components(path, what)
    _no_symlink_ancestors(absolute, what, include_last=True)
    if not stat.S_ISREG(os.lstat(absolute).st_mode):
        raise RepairError(f"{what}: not a regular file")
    return absolute


def _resolve_table_dir(path):
    absolute = _components(path, "TAIWAN_TABLE_DIR")
    _no_symlink_ancestors(absolute, "TAIWAN_TABLE_DIR", include_last=True)
    if not stat.S_ISDIR(os.lstat(absolute).st_mode):
        raise RepairError("TAIWAN_TABLE_DIR: not a directory")
    return absolute


def _resolve_output(path):
    absolute = _components(path, "OUTPUT")
    if absolute == "/":
        raise RepairError("OUTPUT: refusing the filesystem root")
    _no_symlink_ancestors(absolute, "OUTPUT", include_last=False)
    try:
        st = os.lstat(os.path.dirname(absolute))
    except OSError as error:
        raise RepairError(f"OUTPUT: parent cannot be inspected ({_why(error)})") from None
    if not stat.S_ISDIR(st.st_mode):
        raise RepairError("OUTPUT: parent is not a directory")
    try:
        os.lstat(absolute)
    except FileNotFoundError:
        return absolute
    except OSError as error:
        raise RepairError(f"OUTPUT: cannot inspect ({_why(error)})") from None
    raise RepairError("OUTPUT: already exists (including a dangling link); refusing to overwrite")


def _within(child, parent):
    return child == parent or child.startswith(parent.rstrip("/") + "/")


# ---------------------------------------------------------------- sources


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, stat.S_IFMT(st.st_mode))


class Source:
    """One input held open on one owned descriptor for the whole run."""

    def __init__(self, role, path, pin):
        self.role = role
        self.path = path
        self.pin = pin
        self.fd = None
        self.identity = None

    def open(self):
        try:
            self.fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK | _O_NOFOLLOW | _O_CLOEXEC)
        except OSError as error:
            raise RepairError(f"{self.role}: cannot open ({_why(error)})") from None
        st = os.fstat(self.fd)
        if not stat.S_ISREG(st.st_mode):
            raise RepairError(f"{self.role}: descriptor is not a regular file")
        self.identity = _identity(st)
        self.check_stable()
        if st.st_size != self.pin["bytes"]:
            raise RepairError(f"{self.role}: size differs from the pinned length")

    def check_stable(self):
        """The descriptor and the path still name the same unchanged file."""
        try:
            now_fd = _identity(os.fstat(self.fd))
            now_path = _identity(os.lstat(self.path))
        except OSError as error:
            raise RepairError(f"{self.role}: cannot re-inspect source ({_why(error)})") from None
        if now_fd != self.identity or now_path != self.identity:
            raise RepairError(f"{self.role}: source identity or metadata changed during the run")

    def read_whole(self, cap):
        """Bounded whole read from offset 0; exact length, EOF and hash."""
        if self.pin["bytes"] > cap:
            raise RepairError(f"{self.role}: pin exceeds the read cap")
        os.lseek(self.fd, 0, os.SEEK_SET)
        data = bytearray()
        while len(data) <= self.pin["bytes"]:
            try:
                chunk = os.read(self.fd, min(CHUNK, self.pin["bytes"] + 1 - len(data)))
            except OSError as error:
                raise RepairError(f"{self.role}: read failed ({_why(error)})") from None
            if not chunk:
                break
            data += chunk
        if len(data) != self.pin["bytes"]:
            raise RepairError(f"{self.role}: read length differs from the pinned length")
        data = bytes(data)
        if _sha(data) != self.pin["sha256"]:
            raise RepairError(f"{self.role}: SHA-256 differs from the pin")
        self.check_stable()
        return data

    def close(self):
        fd, self.fd = self.fd, None
        if fd is not None:
            try:
                os.close(fd)
            except OSError as error:
                raise RepairError(f"{self.role}: close failed ({_why(error)})") from None


def _generator_identity():
    """Bytes/hash of the generator file actually being executed, read stably."""
    path = os.path.abspath(__file__)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | _O_NOFOLLOW | _O_CLOEXEC)
    except OSError as error:
        raise RepairError(f"generator: cannot open own source ({_why(error)})") from None
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise RepairError("generator: own source is not a regular file")
        data = bytearray()
        while len(data) <= SMALL_CAP:
            chunk = os.read(fd, SMALL_CAP + 1 - len(data))
            if not chunk:
                break
            data += chunk
        if _identity(os.fstat(fd)) != _identity(before) or _identity(os.lstat(path)) != _identity(before):
            raise RepairError("generator: own source changed while it was read")
    finally:
        os.close(fd)
    if len(data) > SMALL_CAP or len(data) != before.st_size:
        raise RepairError("generator: own source is unbounded or changed length")
    return {"file": os.path.basename(path), "bytes": len(data), "sha256": _sha(bytes(data))}


# ---------------------------------------------------------------- output


def _package_dirs(profile):
    name = profile["package"]["name"]
    dirs = [".", name]
    for part in ("data", "luafiles514", "lua files", "navigation"):
        dirs.append(dirs[-1] + "/" + part)
    return dirs


def _payload_files(profile):
    files = [BUNDLE_OUT, profile["package"]["name"] + "/mod.json"]
    files += [request["target"] for request in profile["requests"]]
    return sorted(files)


class Output:
    """The new OUTPUT tree. Records what this run created, by identity."""

    def __init__(self, root):
        self.root = root
        self.created = []  # (relative path, dev, ino, is_dir), creation order
        self.records = {}  # relative path -> {path, bytes, sha256, mode}
        self.root_created_unverified = False

    def path(self, relative):
        return self.root if relative == "." else os.path.join(self.root, relative)

    def mkdir(self, relative):
        target = self.path(relative)
        try:
            os.mkdir(target, DIR_MODE)
        except OSError as error:
            raise RepairError(f"cannot create directory {relative} ({_why(error)})") from None
        if relative == ".":
            self.root_created_unverified = True
        st = os.lstat(target)
        if not stat.S_ISDIR(st.st_mode):
            raise RepairError(f"created directory {relative} is not a directory")
        self.created.append((relative, st.st_dev, st.st_ino, True))
        if relative == ".":
            self.root_created_unverified = False
        # A restrictive umask may have removed bits: set the exact mode on the
        # directory just created, then confirm identity and mode.
        os.chmod(target, DIR_MODE)
        after = os.lstat(target)
        if (after.st_dev, after.st_ino) != (st.st_dev, st.st_ino) or not stat.S_ISDIR(after.st_mode):
            raise RepairError(f"directory {relative} was replaced")
        if stat.S_IMODE(after.st_mode) != DIR_MODE:
            raise RepairError(f"directory {relative} does not have mode 0700")

    def _create(self, relative):
        target = self.path(relative)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW | _O_CLOEXEC
        try:
            fd = os.open(target, flags, FILE_MODE)
        except OSError as error:
            raise RepairError(f"cannot create {relative} ({_why(error)})") from None
        try:
            st = os.fstat(fd)
            self.created.append((relative, st.st_dev, st.st_ino, False))
            os.fchmod(fd, FILE_MODE)
        except BaseException:
            os.close(fd)
            raise
        return fd

    @staticmethod
    def _write_all(fd, data, relative):
        view = memoryview(data)
        while view:
            try:
                written = os.write(fd, view)
            except OSError as error:
                raise RepairError(f"write failed for {relative} ({_why(error)})") from None
            if not isinstance(written, int) or written <= 0 or written > len(view):
                raise RepairError(f"write made no valid progress for {relative}")
            view = view[written:]

    @staticmethod
    def _finish(fd, relative):
        """fsync and close one written file; close is attempted exactly once."""
        try:
            try:
                os.fsync(fd)
            except OSError as error:
                raise RepairError(f"fsync failed for {relative} ({_why(error)})") from None
        finally:
            try:
                os.close(fd)
            except OSError as error:
                raise RepairError(f"close failed for {relative} ({_why(error)})") from None

    def write_bytes(self, relative, data):
        fd = self._create(relative)
        try:
            self._write_all(fd, data, relative)
        except BaseException:
            os.close(fd)
            raise
        self._finish(fd, relative)
        return self.read_back(relative, len(data), _sha(data))

    def copy_stream(self, relative, source):
        """Stream one opaque chunk into a new file; never accumulate or parse it."""
        expected = source.pin["bytes"]
        fd = self._create(relative)
        digest = hashlib.sha256()
        total = 0
        try:
            os.lseek(source.fd, 0, os.SEEK_SET)
            while total < expected:
                try:
                    chunk = os.read(source.fd, min(CHUNK, expected - total))
                except OSError as error:
                    raise RepairError(f"{source.role}: read failed ({_why(error)})") from None
                if not chunk:
                    raise RepairError(f"{source.role}: truncated before the pinned length")
                digest.update(chunk)
                total += len(chunk)
                self._write_all(fd, chunk, relative)
            try:
                extra = os.read(source.fd, 1)
            except OSError as error:
                raise RepairError(f"{source.role}: read failed ({_why(error)})") from None
            if extra:
                raise RepairError(f"{source.role}: more bytes than the pinned length")
        except BaseException:
            os.close(fd)
            raise
        self._finish(fd, relative)
        streamed = digest.hexdigest()
        if streamed != source.pin["sha256"]:
            raise RepairError(f"{source.role}: streamed SHA-256 differs from the pin")
        source.check_stable()
        return self.read_back(relative, expected, streamed)

    def read_back(self, relative, size, sha256):
        """Reopen a closed file; check identity, mode, size and hash."""
        target = self.path(relative)
        try:
            fd = os.open(target, os.O_RDONLY | os.O_NONBLOCK | _O_NOFOLLOW | _O_CLOEXEC)
        except OSError as error:
            raise RepairError(f"read-back cannot open {relative} ({_why(error)})") from None
        digest = hashlib.sha256()
        total = 0
        try:
            st = os.fstat(fd)
            owned = [c for c in self.created if c[0] == relative]
            if not owned or (st.st_dev, st.st_ino) != owned[-1][1:3] or not stat.S_ISREG(st.st_mode):
                raise RepairError(f"read-back of {relative} found a different file")
            if stat.S_IMODE(st.st_mode) != FILE_MODE:
                raise RepairError(f"read-back of {relative} found mode other than 0600")
            while total <= size:
                try:
                    chunk = os.read(fd, min(CHUNK, size + 1 - total))
                except OSError as error:
                    raise RepairError(f"read-back of {relative} failed ({_why(error)})") from None
                if not chunk:
                    break
                total += len(chunk)
                digest.update(chunk)
        finally:
            try:
                os.close(fd)
            except OSError as error:
                raise RepairError(f"read-back close failed for {relative} ({_why(error)})") from None
        if total != size or digest.hexdigest() != sha256:
            raise RepairError(f"read-back of {relative} does not match what was written")
        record = {"path": relative, "bytes": size, "sha256": sha256, "mode": "0600"}
        self.records[relative] = record
        return record

    def check_tree(self, dirs, expected_files):
        """Exactly the fixed directories (0700) and files (0600); nothing else."""
        found_files = set()
        for relative in dirs:
            st = os.lstat(self.path(relative))
            if not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode) != DIR_MODE:
                raise RepairError(f"directory {relative} is not a 0700 directory")
            for name in os.listdir(self.path(relative)):
                child = name if relative == "." else relative + "/" + name
                cst = os.lstat(self.path(child))
                if stat.S_ISDIR(cst.st_mode):
                    if child not in dirs:
                        raise RepairError("unexpected directory in the output tree")
                elif stat.S_ISREG(cst.st_mode) and stat.S_IMODE(cst.st_mode) == FILE_MODE:
                    found_files.add(child)
                else:
                    raise RepairError("unexpected entry in the output tree")
        if found_files != set(expected_files):
            raise RepairError("output tree files differ from the fixed list")

    def cleanup(self):
        """Remove only entries this run created, if the root is still ours.

        Returns None when everything owned is gone, else a short reason.
        """
        if not self.created:
            if self.root_created_unverified:
                return "new output root ownership is unverified; it was left untouched"
            return None
        _, dev, ino, _ = self.created[0]
        try:
            st = os.lstat(self.root)
        except FileNotFoundError:
            return None
        except OSError as error:
            return f"cannot inspect output root ({_why(error)})"
        if (st.st_dev, st.st_ino) != (dev, ino) or not stat.S_ISDIR(st.st_mode):
            return "output root was replaced by a foreign entry; it was left untouched"
        left = []
        for relative, dev, ino, is_dir in reversed(self.created):
            target = self.path(relative)
            try:
                st = os.lstat(target)
                if (st.st_dev, st.st_ino) != (dev, ino):
                    left.append(relative)
                    continue
                if is_dir:
                    os.rmdir(target)
                else:
                    os.unlink(target)
            except FileNotFoundError:
                continue
            except OSError:
                left.append(relative)
        if left:
            return f"{len(left)} owned or foreign entr{'y' if len(left) == 1 else 'ies'} could not be removed"
        return None


# ---------------------------------------------------------------- build


def build(bundle_path, table_dir, output_path, profile=PROFILE, *, _emit=None):
    """Create OUTPUT. Returns the success stdout value. `profile` is fixed in production."""
    pins = {pin["role"]: pin for pin in profile["inputs"]}
    bundle_abs = _resolve_source(bundle_path, "BUNDLE_SOURCE")
    tables_abs = _resolve_table_dir(table_dir)
    resolved = {"bundle": bundle_abs}
    for request in profile["requests"]:
        role = request["role"]
        resolved[role] = _resolve_source(os.path.join(tables_abs, pins[role]["file"]), role + " table")
    output_root = _resolve_output(output_path)

    # Path overlap: distinct sources, and OUTPUT neither at nor around any of them.
    if len(set(resolved.values())) != len(resolved):
        raise RepairError("path overlap: the same path is given for two sources")
    for path in list(resolved.values()) + [tables_abs]:
        if _within(path, output_root) or _within(output_root, path):
            raise RepairError("path overlap: OUTPUT overlaps a source path")

    generator = _generator_identity()
    order = ["bundle"] + [request["role"] for request in profile["requests"]]
    sources = {role: Source(role, resolved[role], pins[role]) for role in order}
    output = Output(output_root)
    package = profile["package"]["name"]
    dirs = _package_dirs(profile)
    payload = _payload_files(profile)
    failure = None
    result = None
    try:
        for role in order:
            sources[role].open()
        if len({(s.identity[0], s.identity[1]) for s in sources.values()}) != len(order):
            raise RepairError("path overlap: two source paths name the same file")
        repaired = repair_bundle(sources["bundle"].read_whole(BUNDLE_CAP), profile)
        sources["bundle"].check_stable()

        for relative in dirs:
            output.mkdir(relative)
        files = {}
        files[BUNDLE_OUT] = output.write_bytes(BUNDLE_OUT, repaired)
        mod_json = canonical(profile["package"])
        if (len(mod_json), _sha(mod_json)) != (profile["mod_json"]["bytes"], profile["mod_json"]["sha256"]):
            raise RepairError("mod.json differs from its pin")
        files[package + "/mod.json"] = output.write_bytes(package + "/mod.json", mod_json)
        for request in profile["requests"]:
            source = sources[request["role"]]
            record = output.copy_stream(request["target"], source)
            if (record["bytes"], record["sha256"]) != (source.pin["bytes"], source.pin["sha256"]):
                raise RepairError(f"{request['role']}: alias identity differs from its source")
            files[request["target"]] = record
        for role in order:
            sources[role].check_stable()
        for role in order:
            sources[role].close()

        manifest = {
            "schema": 1,
            "task": TASK,
            "profile": profile["profile"],
            "generator": generator,
            "inputs": profile["inputs"],
            "package": profile["package"],
            "files": [files[path] for path in payload],
        }
        manifest_bytes = canonical(manifest)
        manifest_record = output.write_bytes(MANIFEST, manifest_bytes)
        output.check_tree(dirs, payload + [MANIFEST])

        complete = canonical({
            "schema": 1,
            "task": TASK,
            "profile": profile["profile"],
            "state": "complete",
            "files": len(payload),
            "manifest": {"file": MANIFEST, "bytes": manifest_record["bytes"],
                         "sha256": manifest_record["sha256"]},
        })
        # Written beside, read back, then linked into place (never over an entry).
        output.write_bytes(COMPLETE_PARTIAL, complete)
        try:
            os.link(output.path(COMPLETE_PARTIAL), output.path(COMPLETE), follow_symlinks=False)
        except OSError as error:
            raise RepairError(f"cannot finalize completion ({_why(error)})") from None
        st = os.lstat(output.path(COMPLETE))
        output.created.append((COMPLETE, st.st_dev, st.st_ino, False))
        try:
            os.unlink(output.path(COMPLETE_PARTIAL))
        except OSError as error:
            raise RepairError(f"cannot finalize completion ({_why(error)})") from None
        output.read_back(COMPLETE, len(complete), _sha(complete))
        output.check_tree(dirs, payload + [MANIFEST, COMPLETE])
        result = {
            "task": TASK,
            "state": "complete",
            "output": os.path.basename(output_root),
            "files": len(payload),
            "manifest_sha256": manifest_record["sha256"],
        }
        if _emit is not None:
            _emit(result)
    except BaseException as error:
        failure = error
    finally:
        for source in sources.values():
            try:
                source.close()
            except RepairError as error:
                if failure is None:
                    failure = error
    if failure is not None:
        problem = output.cleanup()
        if problem is not None:
            if isinstance(failure, RepairError):
                raise RepairError(f"{failure}; cleanup: {problem}") from None
            raise RepairError(f"internal {type(failure).__name__}; cleanup: {problem}") from None
        raise failure
    return result


def _write_success(result):
    text = json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n"
    if sys.stdout.write(text) != len(text):
        raise RepairError("stdout write incomplete")
    sys.stdout.flush()


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3 or any(a.startswith("-") for a in args):
        sys.stderr.write("usage: navigation_client_repair.py BUNDLE_SOURCE TAIWAN_TABLE_DIR OUTPUT\n")
        return 2
    try:
        build(*args, _emit=_write_success)
    except RepairError as error:
        sys.stderr.write(f"navigation_client_repair: refused/failed: {error}\n")
        return 1
    except OSError as error:
        sys.stderr.write(f"navigation_client_repair: failed: {_why(error)}\n")
        return 1
    except Exception as error:  # bounded diagnosis, never a traceback
        sys.stderr.write(f"navigation_client_repair: failed: internal {type(error).__name__}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
