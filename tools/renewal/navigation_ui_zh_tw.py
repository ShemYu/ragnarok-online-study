"""Fixed-input Navigation Traditional Chinese source transform (T05.009).

    import navigation_ui_zh_tw as nav
    localized = nav.transform_bundle(original)   # bytes -> bytes
    original = nav.restore_bundle(localized)     # exact inverse

Pure functions over one exact repaired Ragnarok Offline 1.6.3 Online.js
(13172839 bytes) and its one exact localized form (13173065 bytes). Exactly
75 fixed edits: 66 English literal sites, 6 Share/Find bitmap attribute
removals, 2 Share/Find caption children and 1 scoped CSS rule. Every other
byte, including the 9700-byte repaired loader, is copied unchanged.

Before building, each direction checks the whole input size/SHA-256 and every
fixed fragment at its fixed span in fixed nonoverlapping order; before
returning it checks the whole result size/SHA-256. Any mismatch raises
ValueError and nothing is returned. The three removed attributes of each
button share one localized point and are restored in bg, hover, down order.

No I/O, environment, network, subprocess or other module is used; nothing
runs at import except a check of the constants below. Standard library only
(Python 3.9). See NAVIGATION_UI_ZH_TW.md.
"""

import hashlib

TASK = "T05.009"
PROFILE = "navigation-ui-zh-tw-v1"

INPUT_BYTES = 13172839
INPUT_SHA256 = "6ba854cb67b1306cadb905b1b89a7a1eac98cd7e5c912196e6f87df41a5c4c2f"
OUTPUT_BYTES = 13173065
OUTPUT_SHA256 = "67525a4ec4b834ec02c5ff33b4ca55c119f1380fa131ea329aab880359144478"
EDIT_COUNT = 75

# (id, original start, original end, localized start, localized end,
#  original source fragment, localized source fragment), in source order.
# Offsets are zero-based half-open UTF-8 byte offsets. Fragments are compiled
# JS source text: HTML/CSS sit inside JSON-escaped string tokens, so \" and \n
# below are the literal two-byte escapes found in the bundle.
_EDITS = (
    ('A01-title', 7023217, 7023227, 7023217, 7023223, 'Navigation', '導航'),
    ('A02-caption-ALL', 7023663, 7023666, 7023659, 7023665, 'All', '全部'),
    ('A02-caption-NPC', 7023697, 7023700, 7023696, 7023702, 'NPC', '人物'),
    ('A02-caption-MOB', 7023731, 7023734, 7023733, 7023739, 'MOB', '魔物'),
    ('A03-prefix', 7024121, 7024135, 7024126, 7024139, 'Search result[', '搜尋結果['),
    ('A04-detail-initial', 7024333, 7024348, 7024337, 7024352, 'Select a result', '請選擇結果'),
    ('A05-map', 7024842, 7024845, 7024846, 7024852, 'Map', '地圖'),
    ('A05-coordinates', 7024858, 7024869, 7024865, 7024871, 'Coordinates', '座標'),
    ('A05-frequency', 7024882, 7024891, 7024884, 7024893, 'Frequency', '出現量'),
    ('A12-share-remove-bg', 7025088, 7025138, 7025090, 7025090, ' bg=\\"navigation_interface3/btn_share_normal.bmp\\"', ''),
    ('A12-share-remove-hover', 7025138, 7025189, 7025090, 7025090, ' hover=\\"navigation_interface3/btn_share_over.bmp\\"', ''),
    ('A12-share-remove-down', 7025189, 7025240, 7025090, 7025090, ' down=\\"navigation_interface3/btn_share_press.bmp\\"', ''),
    ('A06-share-tooltip', 7025249, 7025277, 7025099, 7025126, 'Not supported by this client', '此用戶端不支援分享'),
    ('A12-share-insert-child', 7025280, 7025280, 7025129, 7025135, '', '分享'),
    ('A12-find-remove-bg', 7025350, 7025399, 7025205, 7025205, ' bg=\\"navigation_interface3/btn_find_normal.bmp\\"', ''),
    ('A12-find-remove-hover', 7025399, 7025449, 7025205, 7025205, ' hover=\\"navigation_interface3/btn_find_over.bmp\\"', ''),
    ('A12-find-remove-down', 7025449, 7025499, 7025205, 7025205, ' down=\\"navigation_interface3/btn_find_press.bmp\\"', ''),
    ('A12-find-insert-child', 7025500, 7025500, 7025206, 7025212, '', '尋路'),
    ('A07-services', 7025744, 7025753, 7025456, 7025463, ' Services', ' 服務'),
    ('A08-move', 7025855, 7025863, 7025565, 7025575, '✣ MOVE', '✣ 移動'),
    ('A09-minimize', 7026011, 7026020, 7025723, 7025730, ' Minimize', ' 縮小'),
    ('A10-mouse', 7026149, 7026155, 7025859, 7025868, 'Mouse:', '滑鼠：'),
    ('A10-target', 7026265, 7026272, 7025978, 7025987, 'Target:', '目標：'),
    ('A11-marker-tooltip', 7026572, 7026583, 7026287, 7026299, 'Path marker', '路徑標記'),
    ('A12-action-button-css', 7033941, 7034008, 7033657, 7034326,
     '.Navigation .search-actions ui-button { width:120px; height:20px; }',
     '.Navigation .search-actions ui-button { width:120px; height:20px; box-sizing:border-box; display:inline-flex; align-items:center; justify-content:center; border:1px solid #9c9c9c; border-radius:2px; background:linear-gradient(#fff,#e4e4e4); color:#333; line-height:18px; white-space:nowrap; user-select:none; cursor:pointer; }\\n'
     '.Navigation .search-actions ui-button:not([disabled]):hover { background:linear-gradient(#fff,#e2efff); border-color:#7d9abb; }\\n'
     '.Navigation .search-actions ui-button:not([disabled]):active { background:linear-gradient(#bfd5ef,#e1edfa); border-color:#627f9f; }\\n'
     '.Navigation .search-actions ui-button[disabled] { opacity:.5; cursor:default; }'),
    ('B14-no-path', 7042959, 7042975, 7043277, 7043299, ' (no path found)', ' （找不到路徑）'),
    ('B01-short-query', 7063946, 7063961, 7064270, 7064285, 'Select a result', '請選擇結果'),
    ('B05-mapwide', 7071538, 7071552, 7071862, 7071877, 'Map-wide spawn', '全地圖出現'),
    ('B06-label-level', 7072639, 7072642, 7072964, 7072970, 'Lv.', '等級'),
    ('B06-label-element', 7072679, 7072686, 7073007, 7073013, 'Element', '屬性'),
    ('B07-stat-unknown-element', 7072708, 7072715, 7073035, 7073041, 'Unknown', '未知'),
    ('B06-label-race', 7072731, 7072735, 7073057, 7073063, 'Type', '種族'),
    ('B07-stat-unknown-race', 7072754, 7072761, 7073082, 7073088, 'Unknown', '未知'),
    ('B06-label-size', 7072777, 7072781, 7073104, 7073110, 'Size', '體型'),
    ('B07-stat-unknown-size', 7072800, 7072807, 7073129, 7073135, 'Unknown', '未知'),
    ('B12-spawn-tooltip', 7073649, 7073663, 7073977, 7073993, ' spawn entries', ' 筆出現資料'),
    ('B02-result-select', 7074872, 7074887, 7075202, 7075217, 'Select a result', '請選擇結果'),
    ('B02-result-empty', 7074892, 7074901, 7075222, 7075231, 'No result', '無結果'),
    ('B04-empty-advice', 7075195, 7075298, 7075525, 7075552, 'Empty? An English GRF can replace these tables. Enable Settings → Mods → navigation-english-tables.', '請嘗試其他關鍵字。'),
    ('B03-no-results', 7075933, 7075949, 7076187, 7076202, 'No results found', '找不到結果'),
    ('B13-map-click', 7080444, 7080453, 7080697, 7080709, 'Map Click', '地圖選點'),
    ('B15-navi-help', 8809814, 8809891, 8810070, 8810145, 'Navigate by coordinates or search by name. Usage: /navi map x/y or /navi name', '以座標或名稱導航。用法：/navi prontera 150/150 或 /navi 波利'),
    ('B08-0-Neutral', 10830219, 10830226, 10830473, 10830476, 'Neutral', '無'),
    ('B08-1-Water', 10830230, 10830235, 10830480, 10830483, 'Water', '水'),
    ('B08-2-Earth', 10830239, 10830244, 10830487, 10830490, 'Earth', '地'),
    ('B08-3-Fire', 10830248, 10830252, 10830494, 10830497, 'Fire', '火'),
    ('B08-4-Wind', 10830256, 10830260, 10830501, 10830504, 'Wind', '風'),
    ('B08-5-Poison', 10830264, 10830270, 10830508, 10830511, 'Poison', '毒'),
    ('B08-6-Holy', 10830274, 10830278, 10830515, 10830518, 'Holy', '聖'),
    ('B08-7-Shadow', 10830282, 10830288, 10830522, 10830525, 'Shadow', '暗'),
    ('B08-8-Ghost', 10830292, 10830297, 10830529, 10830532, 'Ghost', '念'),
    ('B08-9-Undead', 10830301, 10830307, 10830536, 10830542, 'Undead', '不死'),
    ('B09-0-Formless', 10830334, 10830342, 10830569, 10830575, 'Formless', '無形'),
    ('B09-1-Undead', 10830346, 10830352, 10830579, 10830585, 'Undead', '不死'),
    ('B09-2-Brute', 10830356, 10830361, 10830589, 10830595, 'Brute', '動物'),
    ('B09-3-Plant', 10830365, 10830370, 10830599, 10830605, 'Plant', '植物'),
    ('B09-4-Insect', 10830374, 10830380, 10830609, 10830615, 'Insect', '昆蟲'),
    ('B09-5-Fish', 10830384, 10830388, 10830619, 10830625, 'Fish', '魚貝'),
    ('B09-6-Demon', 10830392, 10830397, 10830629, 10830635, 'Demon', '惡魔'),
    ('B09-7-Demi-Human', 10830401, 10830411, 10830639, 10830645, 'Demi-Human', '人形'),
    ('B09-8-Angel', 10830415, 10830420, 10830649, 10830655, 'Angel', '天使'),
    ('B09-9-Dragon', 10830424, 10830430, 10830659, 10830662, 'Dragon', '龍'),
    ('B09-10-Player', 10830434, 10830440, 10830666, 10830672, 'Player', '玩家'),
    ('B09-11-Boss', 10830444, 10830448, 10830676, 10830682, 'Boss', '首領'),
    ('B10-0-Small', 10830475, 10830480, 10830709, 10830715, 'Small', '小型'),
    ('B10-1-Medium', 10830484, 10830490, 10830719, 10830725, 'Medium', '中型'),
    ('B10-2-Large', 10830494, 10830499, 10830729, 10830735, 'Large', '大型'),
    ('B11-0-Very Low', 10831465, 10831473, 10831701, 10831707, 'Very Low', '極少'),
    ('B11-1-Low', 10831501, 10831504, 10831735, 10831738, 'Low', '少'),
    ('B11-2-Average', 10831532, 10831539, 10831766, 10831772, 'Average', '普通'),
    ('B11-3-High', 10831567, 10831571, 10831800, 10831803, 'High', '多'),
    ('B11-4-Very High', 10831582, 10831591, 10831814, 10831820, 'Very High', '極多'),
    ('B07-db-unknown-element', 10831810, 10831817, 10832039, 10832045, 'Unknown', '未知'),
    ('B07-db-unknown-race', 10831903, 10831910, 10832131, 10832137, 'Unknown', '未知'),
    ('B07-db-unknown-size', 10831966, 10831973, 10832193, 10832199, 'Unknown', '未知'),
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
    at its [start, end) in nondecreasing nonoverlapping order; equal points
    keep their listed order. The result must be `result_size`/`result_sha256`.
    """
    if type(data) is not bytes:
        raise ValueError("%s: expected bytes, got %s" % (what, type(data).__name__))
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
    """Return the localized bundle for the exact original Online.js bytes."""
    return _splice(source, [(n, a, b, old, new) for n, a, b, _, _, old, new in _PLAN],
                   INPUT_BYTES, INPUT_SHA256, OUTPUT_BYTES, OUTPUT_SHA256,
                   "transform_bundle")


def restore_bundle(localized: bytes) -> bytes:
    """Return the exact original Online.js bytes for the localized bundle."""
    return _splice(localized, [(n, c, d, new, old) for n, _, _, c, d, old, new in _PLAN],
                   OUTPUT_BYTES, OUTPUT_SHA256, INPUT_BYTES, INPUT_SHA256,
                   "restore_bundle")
