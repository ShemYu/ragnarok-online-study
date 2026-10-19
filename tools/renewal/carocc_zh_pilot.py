#!/usr/bin/env python3
"""Generate the tw-carocc-pilot mod: a Traditional Chinese Captain Carocc pilot.

The input is the pinned rAthena `academy.txt` packaged with Ragnarok Offline
v1.6.3 (CP949 file; the Carocc block itself is ASCII). Only its Izlude Captain
Carocc `script` block (lines 388-798) is copied, under the new internal name
`Captain Carocc#t05zh`. Exactly nine display literals are translated: the two
opening `mes` lines, the three `case 1` (Hello?) `mes` lines, the three
labels of that `select` and, since 0.2.0, the one active-7472 revisit `mes`
sentence on line 693 that carries the <NAVI>[Hun] link; its NAVI markup is kept
byte for byte inside the translated literal. Every other byte of the block is
kept, including its own OnInit/OnTouch, tabs and line endings. A separate
hidden controller, `T05CaroccZHInit`, disables the stock `Captain Carocc#iz`
from OnInit.

Masking the nine translations and the header name back must reproduce the
source block byte for byte; this is checked before anything is written.
Standard library only. The input is only read. Output is never overwritten.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile

VERSION = "0.2.0"
MOD_NAME = "tw-carocc-pilot"
SCRIPT_PATH = "npc/carocc_zh_pilot.txt"
MOD_JSON = {
    "name": MOD_NAME,
    "version": VERSION,
    "author": "local generator (T05.001)",
    "description": "Pilot: Captain Carocc in Izlude greets new Novices in Traditional "
                   "Chinese (opening, Hello? reply and menu) and translates one active-7472 "
                   "revisit NAVI sentence. Other text remains subject to existing client "
                   "translation or English fallback.",
    "requires": {"app": ">=1.6.3", "era": "renewal"},
}

STOCK_NAME = b"Captain Carocc#iz"
CLONE_NAME = b"Captain Carocc#t05zh"
CONTROLLER_NAME = b"T05CaroccZHInit"


class PilotError(ValueError):
    pass


class Source:
    """What the input must be, and where the Carocc block sits in it."""

    def __init__(self, sha256, size, first, last, block_sha256, header, duplicates):
        self.sha256, self.size = sha256, size
        self.first, self.last = first, last  # 1-based, inclusive
        self.block_sha256 = block_sha256
        self.header = header
        self.duplicates = duplicates  # 1-based lines of excluded duplicate() definitions


PINNED = Source(
    sha256="b2ab5f7de7e1c36e4f58b8447a80d4cb089e8bf45aeade59953c6a70004f27fd",
    size=508418,
    first=388,
    last=798,
    block_sha256="f9d8d5565a228492f7e50172aa360936522e72889b574ac3b404e443b2096e33",
    header=b"izlude,198,213,3\tscript\tCaptain Carocc#iz\t4_M_REINDEER,5,5,{",
    duplicates=(800, 801, 802, 803),
)

# (source line, kind, English literal, Traditional Chinese). Latin proper names
# Carocc/Izlude are kept: their official Chinese forms are not established.
# The ninth entry (active-7472 revisit) keeps its <NAVI>...</NAVI> link bytes,
# [Hun] name and izlude,122,207 target verbatim; only the prose around it changes.
TRANSLATIONS = (
    (569, "mes", "Hello?", "你好？"),
    (570, "mes", "Is it your first time on Izlude?", "你是第一次來到 Izlude 嗎？"),
    (572, "select", "Hello?", "你好？"),
    (572, "select", "Let me get on the ship!", "讓我上船吧！"),
    (572, "select", "I don't know what to do.", "我不知道該做什麼。"),
    (575, "mes", "You look strong and able!", "你看起來既強壯又能幹！"),
    (576, "mes", "I like able people like you!", "我就喜歡像你這樣能幹的人！"),
    (577, "mes", "Always be healthy and strong as you are now.", "希望你永遠都像現在這樣健康又強壯。"),
    (693, "mes", "My friend <NAVI>[Hun]<INFO>izlude,122,207</INFO></NAVI> will be around the academy entrance.",
     "我的朋友 <NAVI>[Hun]<INFO>izlude,122,207</INFO></NAVI> 就在學院入口附近。"),
)

LIMITS = (
    "Only the novice first-visit opening, its menu, the Hello? reply and one active-7472 revisit "
    "NAVI sentence are authored in Chinese; all other source literals remain unchanged and use "
    "existing client translation or English fallback.",
    "Speaker tag [Carocc] and the Latin names Carocc/Izlude are kept as in the source.",
    "Duplicates on izlude_a..izlude_d (source lines 800-803) are not copied or disabled; they stay English.",
    "No runtime check: loading, client rendering and dialogue flow are verified by the coordinator.",
)


def split_lines(data):
    """Lines with their b'\\n' kept. Only LF splits; other bytes stay inside lines."""
    parts = data.split(b"\n")
    lines = [p + b"\n" for p in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def script_literal(text, kind):
    """The bytes of a translated rAthena string literal body, or PilotError.

    Nothing is escaped: characters that would need escaping, colour codes (^),
    controls and, in select labels, the ':' option separator are refused.
    """
    if not isinstance(text, str) or not text.strip():
        raise PilotError(f"translation {text!r} is empty")
    for ch in text:
        if ch in '"\\^' or ord(ch) < 0x20 or ord(ch) == 0x7f or ch in "  ﻿":
            raise PilotError(f"translation {text!r} contains unsupported character {ch!r}")
        if kind == "select" and ch == ":":
            raise PilotError(f"select label {text!r} contains ':', which splits menu options")
    if not any(0x3400 <= ord(ch) <= 0x9fff for ch in text):
        raise PilotError(f"translation {text!r} has no Chinese characters")
    return text.encode("utf-8")


def literal_span(line, literal, where):
    """Start/end of the single quoted occurrence of literal in line."""
    quoted = b'"' + literal + b'"'
    count = line.count(quoted)
    if count != 1:
        state = "missing" if count == 0 else f"ambiguous ({count} matches)"
        raise PilotError(f"{where}: anchor \"{literal.decode('utf-8', 'replace')}\" is {state}")
    start = line.index(quoted) + 1
    return start, start + len(literal)


def replace_literals(line, pairs, where):
    """Replace each (old, new) quoted literal by position; spans must not overlap."""
    spans = sorted((literal_span(line, old, where) + (new,)) for old, new in pairs)
    for (_, end, _), (start, _, _) in zip(spans, spans[1:]):
        if start < end:
            raise PilotError(f"{where}: anchors overlap")
    out, pos = b"", 0
    for start, end, new in spans:
        out += line[pos:start] + new
        pos = end
    return out + line[pos:]


def check_kind(line, kind, english, where):
    body = re.escape(english)
    if kind == "mes":
        if not re.fullmatch(rb'\t*mes "' + body + rb'";\n', line):
            raise PilotError(f"{where}: expected a lone mes line for this anchor")
    elif kind == "select":
        if b"select(" not in line:
            raise PilotError(f"{where}: expected a select( line for this anchor")
    else:
        raise PilotError(f"{where}: unknown kind {kind}")


def grouped(translations, source):
    """{block index: [(kind, english bytes, chinese bytes), ...]} in source order."""
    by_line = {}
    for number, kind, english, chinese in translations:
        if not source.first < number <= source.last:
            raise PilotError(f"line {number}: translation outside the block body")
        by_line.setdefault(number - source.first, []).append(
            (kind, english.encode("ascii"), script_literal(chinese, kind)))
    return by_line


def build_block(block, source, by_line):
    out = list(block)
    stock_field, clone_field = b"\t" + STOCK_NAME + b"\t", b"\t" + CLONE_NAME + b"\t"
    if block[0].count(stock_field) != 1:
        raise PilotError("header: stock NPC name is missing or ambiguous")
    out[0] = block[0].replace(stock_field, clone_field)
    for index, items in by_line.items():
        where = f"line {source.first + index}"
        for kind, english, _ in items:
            literal_span(block[index], english, where)
            check_kind(block[index], kind, english, where)
        out[index] = replace_literals(block[index], [(e, c) for _, e, c in items], where)
    return out


def mask_back(out_block, source, by_line):
    """Independently undo the allowed changes; the result must equal the source block."""
    restored = list(out_block)
    clone_field, stock_field = b"\t" + CLONE_NAME + b"\t", b"\t" + STOCK_NAME + b"\t"
    if out_block[0].count(clone_field) != 1:
        raise PilotError("generated header does not carry the clone name exactly once")
    restored[0] = out_block[0].replace(clone_field, stock_field)
    for index, items in by_line.items():
        restored[index] = replace_literals(
            out_block[index], [(c, e) for _, e, c in items], f"mask line {source.first + index}")
    return restored


def controller():
    return (b"-\tscript\t" + CONTROLLER_NAME + b"\t-1,{\n"
            b"\tend;\n"
            b"OnInit:\n"
            b"\tdisablenpc \"" + STOCK_NAME + b"\";\n"
            b"\tend;\n"
            b"}\n")


def provenance(source):
    lines = (
        f"//===== {MOD_NAME} {VERSION} (generated by tools/renewal/carocc_zh_pilot.py, T05.001) =====",
        "//= Source: rAthena script academy.txt (Criatura Academy), as packaged in",
        f"//=   Ragnarok Offline v1.6.3; SHA-256 {source.sha256}, {source.size} bytes.",
        f"//=   Copied: the Captain Carocc script block, source lines {source.first}-{source.last}.",
        "//= Original authors per the source header: Kisuka, Capuche, Jenkijo, mundussan.",
        "//= rAthena scripts are free software under the GNU General Public License v3;",
        "//=   this is a modified copy distributed under the same licence.",
        "//= Changes: internal NPC name Captain Carocc#iz -> Captain Carocc#t05zh;",
        f"//=   {len(TRANSLATIONS)} display literals translated to Traditional Chinese (UTF-8);",
        f"//=   controller {CONTROLLER_NAME.decode()} disables the stock Captain Carocc#iz.",
        "//= Disable this mod and restart to get the stock English NPC back.",
        "//==============================================================================",
    )
    return "".join(line + "\n" for line in lines).encode("ascii")


def generate(data, source=PINNED, translations=TRANSLATIONS):
    """Return (script_bytes, metadata) for validated input bytes."""
    if len(data) != source.size:
        raise PilotError(f"input is {len(data)} bytes, expected {source.size}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != source.sha256:
        raise PilotError(f"input SHA-256 {digest} is not the pinned academy.txt {source.sha256}")
    lines = split_lines(data)
    if len(lines) < max((source.last,) + tuple(source.duplicates)):
        raise PilotError("input ends before the expected Carocc block")
    block = lines[source.first - 1:source.last]
    if block[0] != source.header + b"\n" or block[-1] != b"}\n":
        raise PilotError("block boundaries do not match the expected Carocc header/closing brace")
    raw_block = b"".join(block)
    if hashlib.sha256(raw_block).hexdigest() != source.block_sha256:
        raise PilotError("Carocc block bytes differ from the pinned block")
    definition = re.compile(rb"[^\t\n]*\tscript\t" + re.escape(STOCK_NAME) + rb"\t")
    if sum(1 for line in lines if definition.match(line)) != 1:
        raise PilotError("stock Captain Carocc#iz script definition is missing or not unique")
    for name in (CLONE_NAME, CONTROLLER_NAME):
        if name in data:
            raise PilotError(f"{name.decode()} already occurs in the input; name would not be unique")
    dup = re.compile(rb"[^\t\n]*\tduplicate\(" + re.escape(STOCK_NAME) + rb"\)\t")
    excluded = []
    for number in source.duplicates:
        if not dup.match(lines[number - 1]):
            raise PilotError(f"line {number}: expected an excluded duplicate of {STOCK_NAME.decode()}")
        excluded.append(lines[number - 1].rstrip(b"\n").split(b"\t")[2].decode("ascii"))

    by_line = grouped(translations, source)
    out_block = build_block(block, source, by_line)
    if mask_back(out_block, source, by_line) != block:
        raise PilotError("masked output block is not byte-identical to the source block")
    out_raw = b"".join(out_block)
    for token in (b"mes ", b"select(", b"next;", b"close", b"case ", b"getitem", b"warp",
                  b"Zeny", b"getexp", b"setquest", b"completequest", b"viewpoint", b"navigateto", b"cutin"):
        if out_raw.count(token) != raw_block.count(token):
            raise PilotError(f"token {token!r} count changed")
    changed = [i for i, (a, b) in enumerate(zip(block, out_block)) if a != b]
    if changed != [0] + sorted(by_line):
        raise PilotError(f"unexpected changed lines {[source.first + i for i in changed]}")

    script = provenance(source) + b"\n" + out_raw + b"\n" + controller()
    script.decode("utf-8")
    metadata = {
        "generator": "tools/renewal/carocc_zh_pilot.py", "generator_version": VERSION,
        "input": {"name": "academy.txt", "sha256": digest, "bytes": len(data)},
        "block": {"first_line": source.first, "last_line": source.last,
                  "bytes": len(raw_block), "sha256": source.block_sha256,
                  "masked_output_equals_source": True},
        "excluded_duplicates": {"lines": list(source.duplicates), "names": excluded},
        "header": {"stock": STOCK_NAME.decode(), "clone": CLONE_NAME.decode(),
                   "line": out_block[0].rstrip(b"\n").decode("ascii")},
        "controller": {"name": CONTROLLER_NAME.decode(),
                       "on_init": f'disablenpc "{STOCK_NAME.decode()}"; end;'},
        "translations": [{"line": n, "kind": k, "en": e, "zh_hant": z} for n, k, e, z in translations],
        "limits": list(LIMITS),
    }
    return script, metadata


def trusted_parent(out_dir):
    parent = out_dir.absolute().parent
    try:
        info = os.lstat(parent)
    except FileNotFoundError:
        raise PilotError(f"output parent does not exist: {parent}") from None
    if not stat.S_ISDIR(info.st_mode):
        raise PilotError(f"output parent is not a real directory (symlink or file): {parent}")
    if info.st_uid != os.getuid() or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise PilotError(f"output parent must be owned by you and not group/world-writable: {parent}")
    return parent


def refuse_existing(out_dir):
    if out_dir.exists() or out_dir.is_symlink():
        raise PilotError(f"output already exists, refusing to overwrite: {out_dir}")


def write_output(out_dir, script, metadata):
    out_dir = Path(out_dir)
    refuse_existing(out_dir)
    parent = trusted_parent(out_dir)
    mod_json = (json.dumps(MOD_JSON, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    metadata = dict(metadata, output={
        "layout": [f"{MOD_NAME}/mod.json", f"{MOD_NAME}/{SCRIPT_PATH}"],
        SCRIPT_PATH: {"sha256": hashlib.sha256(script).hexdigest(), "bytes": len(script)},
        "mod.json": {"sha256": hashlib.sha256(mod_json).hexdigest(), "bytes": len(mod_json)},
    })
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=parent))
    try:
        mod_dir = staging / MOD_NAME
        (mod_dir / "npc").mkdir(parents=True)
        (mod_dir / SCRIPT_PATH).write_bytes(script)
        (mod_dir / "mod.json").write_bytes(mod_json)
        (staging / "generation-manifest.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # copytree creates the destination with an exclusive mkdir, so a file,
        # directory or (dangling) symlink that appears after the check is refused,
        # never replaced or followed.
        shutil.copytree(staging, out_dir, dirs_exist_ok=False)
    except OSError as exc:
        raise PilotError(f"could not publish output to {out_dir}: {exc}; "
                         "if the destination was created it may be incomplete; inspect it before retrying") from None
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return metadata


def read_input(path):
    with open(path, "rb") as handle:
        size = os.fstat(handle.fileno()).st_size
        if size != PINNED.size:
            raise PilotError(f"input is {size} bytes, expected {PINNED.size}")
        return handle.read(PINNED.size + 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="pinned academy.txt (read-only)")
    parser.add_argument("output", type=Path, help="new output directory (must not exist)")
    args = parser.parse_args(argv)
    try:
        refuse_existing(args.output)
        trusted_parent(args.output)
        script, metadata = generate(read_input(args.input))
        metadata = write_output(args.output, script, metadata)
    except (PilotError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(args.output),
                      "script sha256": metadata["output"][SCRIPT_PATH]["sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
