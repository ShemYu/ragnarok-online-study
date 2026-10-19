"""Fixed-input modern Quest Traditional Chinese chrome transform (T05.011).

    import quest_ui_zh_tw as quest
    localized = quest.transform_bundle(original)   # bytes -> bytes
    original = quest.restore_bundle(localized)     # exact inverse

Pure functions over one exact Chinese-navigation Ragnarok Offline 1.6.3
Online.js (13173065 bytes) and its one exact Quest-localized form (13174160
bytes). Exactly 23 fixed edits, in source order:

- 3 generated templates: the shared QuestCommon hunt messages (Mission /
  you killed, Completed; these also reach QuestV1) and the modern helper
  Deadline. Every compiled ${...} interpolation is kept byte-for-byte.
- 6 hidden Quest/Toggle row fallbacks in the three modern row branches.
- 9 fixed modern list/helper HTML labels.
- 4 span.quest-menu-caption children inserted into the existing empty
  li#active/feature/inactive/cooldown tabs.
- 1 caption CSS block appended to the end of the modern Quest.css token.

Every other byte, including Chinese Navigation, both Close bitmap buttons and
the four bitmap state selections, is copied unchanged.

Before building, each direction checks the whole input size/SHA-256 and every
fixed fragment at its fixed span in fixed nonoverlapping order; before
returning it checks the whole result size/SHA-256. Any mismatch raises
ValueError and nothing is returned. Insertions invert to deletions.

No I/O, environment, network, subprocess or other module is used; nothing
runs at import except a check of the constants below. Standard library only
(Python 3.9). See QUEST_UI_ZH_TW.md.
"""

import hashlib

TASK = "T05.011"
PROFILE = "quest-ui-zh-tw-v1"

INPUT_BYTES = 13173065
INPUT_SHA256 = "67525a4ec4b834ec02c5ff33b4ca55c119f1380fa131ea329aab880359144478"
OUTPUT_BYTES = 13174160
OUTPUT_SHA256 = "9c148d9e43384a2498f9074efd1603b4eda1ff36dac53998985cfdf5eaf6fadf"
EDIT_COUNT = 23

# (id, original start, original end, localized start, localized end,
#  original source fragment, localized source fragment), in source order.
# Offsets are zero-based half-open UTF-8 byte offsets. Fragments are compiled
# JS source text: HTML/CSS sit inside JSON-escaped string tokens, so \" and
# \r\n below are the literal escape bytes found in the bundle.
_EDITS = (
    ('T01-mission', 7943438, 7943613, 7943438, 7943613,
     '`Mission [${DB.getQuestInfo(questID).Title}], you killed [${mob_name}]. (${_questList[questID].hunt_list[huntID].huntCount}/${_questList[questID].hunt_list[huntID].maxCount})`',
     '`任務 [${DB.getQuestInfo(questID).Title}]：已擊倒 [${mob_name}]。(${_questList[questID].hunt_list[huntID].huntCount}/${_questList[questID].hunt_list[huntID].maxCount})`'),
    ('T02-completed', 7943747, 7943772, 7943747, 7943772, '`${mob_name} [Completed]`', '`${mob_name} [已完成]`'),
    ('R-cooldown-icon', 7945961, 7945966, 7945961, 7945967, 'Quest', '任務'),
    ('R-cooldown-toggle', 7946454, 7946460, 7946455, 7946461, 'Toggle', '切換'),
    ('R-active-icon', 7946689, 7946694, 7946690, 7946696, 'Quest', '任務'),
    ('R-active-toggle', 7947239, 7947245, 7947241, 7947247, 'Toggle', '切換'),
    ('R-inactive-icon', 7947456, 7947461, 7947458, 7947464, 'Quest', '任務'),
    ('R-inactive-toggle', 7947977, 7947983, 7947980, 7947986, 'Toggle', '切換'),
    ('T03-deadline', 7964585, 7964619, 7964588, 7964626, '`Deadline [${d.toLocaleString()}]`', '`截止時間 [${d.toLocaleString()}]`'),
    ('H02', 7969154, 7969171, 7969161, 7969173, 'Quest Information', '任務資訊'),
    ('H04', 7969550, 7969561, 7969552, 7969564, 'Description', '任務說明'),
    ('H05', 7969913, 7969920, 7969916, 7969928, 'Monster', '目標魔物'),
    ('H06', 7970306, 7970312, 7970314, 7970326, 'Reward', '任務獎勵'),
    ('H07', 7970538, 7970541, 7970552, 7970567, 'EXP', '基本經驗值'),
    ('H08', 7970677, 7970681, 7970703, 7970718, 'JEXP', '職業經驗值'),
    ('H09', 7970816, 7970820, 7970853, 7970859, 'Item', '物品'),
    ('H01', 7980507, 7980524, 7980546, 7980558, 'Quest Information', '任務資訊'),
    ('I-active', 7980659, 7980659, 7980693, 7980744, '', '<span class=\\"quest-menu-caption\\">進行中</span>'),
    ('I-feature', 7980717, 7980717, 7980802, 7980850, '', '<span class=\\"quest-menu-caption\\">推薦</span>'),
    ('I-inactive', 7980776, 7980776, 7980909, 7980960, '', '<span class=\\"quest-menu-caption\\">暫停中</span>'),
    ('I-cooldown', 7980835, 7980835, 7981019, 7981070, '', '<span class=\\"quest-menu-caption\\">冷卻中</span>'),
    ('H03', 7981346, 7981356, 7981581, 7981593, 'Show Quest', '顯示任務'),
    ('C01-caption-css', 7985922, 7985922, 7986159, 7987017, '',
     '\\r\\n'
     "#Quest .quest-menu-caption { width:30px; height:100px; box-sizing:border-box; display:flex; align-items:center; justify-content:center; writing-mode:vertical-rl; text-orientation:upright; font-family:Arial,'Microsoft JhengHei','PingFang TC',sans-serif; font-size:13px; line-height:18px; letter-spacing:1px; pointer-events:none; user-select:none; background:#e3e7ec; border:1px solid #b3bac4; color:#333; }\\r\\n"
     '#Quest:has(#active-quest-list[style*=\\"display: block\\"]) #active .quest-menu-caption,\\r\\n'
     '#Quest:has(#feature-quest-list[style*=\\"display: block\\"]) #feature .quest-menu-caption,\\r\\n'
     '#Quest:has(#inactive-quest-list[style*=\\"display: block\\"]) #inactive .quest-menu-caption,\\r\\n'
     '#Quest:has(#cooldown-quest-list[style*=\\"display: block\\"]) #cooldown .quest-menu-caption { background:#fff; color:#004c88; font-weight:bold; border-color:#7699bd; }\\r\\n'),
)


def _encode(edits):
    return tuple((name, a, b, c, d, old.encode("utf-8"), new.encode("utf-8"))
                 for name, a, b, c, d, old, new in edits)


def _check_constants(plan, input_bytes, output_bytes):
    # Arithmetic self-consistency only; it reads no bundle bytes.
    if len({row[0] for row in plan}) != len(plan):
        raise RuntimeError("duplicate edit id")
    in_end = out_end = 0
    for name, a, b, c, d, old, new in plan:
        if (a < in_end or c < out_end or b - a != len(old) or d - c != len(new)
                or a - in_end != c - out_end or old == new):
            raise RuntimeError("inconsistent edit constant: %s" % name)
        in_end, out_end = b, d
    if input_bytes - in_end != output_bytes - out_end:
        raise RuntimeError("inconsistent tail length")


_PLAN = _encode(_EDITS)
if len(_PLAN) != EDIT_COUNT:
    raise RuntimeError("edit count is not %d" % EDIT_COUNT)
_check_constants(_PLAN, INPUT_BYTES, OUTPUT_BYTES)
del _EDITS


def _splice(data, sites, size, sha256, result_size, result_sha256, what):
    """Replace each (id, start, end, have, put) site of data, in order.

    data must be exactly `size` bytes with `sha256`, and every `have` must sit
    at its [start, end) in nondecreasing nonoverlapping order. The result must
    be `result_size`/`result_sha256`.
    """
    if type(data) is not bytes:
        raise ValueError("%s: expected bytes" % what)
    if len(data) != size:
        raise ValueError("%s: expected %d bytes, got %d" % (what, size, len(data)))
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError("%s: SHA-256 does not match the fixed input" % what)
    pos = 0
    for name, start, end, have, _ in sites:
        if not (pos <= start <= end <= size) or end - start != len(have):
            raise ValueError("%s: site %s out of order or bounds" % (what, name))
        if not data.startswith(have, start):
            raise ValueError("%s: site %s does not hold its fixed fragment" % (what, name))
        pos = end
    pieces = []
    pos = 0
    for _, start, end, _, put in sites:
        pieces.append(data[pos:start])
        pieces.append(put)
        pos = end
    pieces.append(data[pos:])
    result = b"".join(pieces)
    if len(result) != result_size or hashlib.sha256(result).hexdigest() != result_sha256:
        raise ValueError("%s: result does not match the fixed result pin" % what)
    return result


def transform_bundle(source: bytes) -> bytes:
    """Return the Quest-localized bundle for the exact original Online.js bytes."""
    return _splice(source, [(n, a, b, old, new) for n, a, b, _, _, old, new in _PLAN],
                   INPUT_BYTES, INPUT_SHA256, OUTPUT_BYTES, OUTPUT_SHA256,
                   "transform_bundle")


def restore_bundle(localized: bytes) -> bytes:
    """Return the exact original Online.js bytes for the Quest-localized bundle."""
    return _splice(localized, [(n, c, d, new, old) for n, _, _, c, d, old, new in _PLAN],
                   OUTPUT_BYTES, OUTPUT_SHA256, INPUT_BYTES, INPUT_SHA256,
                   "restore_bundle")
