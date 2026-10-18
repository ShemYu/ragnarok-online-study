#!/usr/bin/env python3
"""Generate the temporary T05.008 navigation browser verifier pages.

    python3 -I -B tools/renewal/navigation_browser_verifier.py API_HTML OUTPUT

API_HTML is the exact pinned production bootstrap (api.html) of the local
game origin. The argument only locates those bytes: every pin, path, origin
and element ID is fixed below and cannot be overridden. OUTPUT is a new 0700
directory holding exactly five 0600 files:

    T05_008-cache.html            standalone six-cache audit/removal/refresh page
    T05_008-cache.mjs             navigation_browser_cache.mjs, byte for byte
    T05_008-original-entry.html   bootstrap pinned to the original Online.js
    T05_008-repaired-entry.html   bootstrap pinned to the repaired Online.js
    verification-manifest.json    sizes/hashes of the inputs and four files

The entry pages keep every bootstrap byte outside the one expression
`import('./' + scriptFile)`, which becomes an inline expression that loads
Online.js through one <script type="module"> carrying the expected SHA-256
integrity, so the browser itself refuses any other bytes. The cache page loads
its module the same way. Nothing here runs a browser, server, cache or game
code; the bootstrap is read as bytes and never executed. Generated files are
not a completion marker. Standard library only (Python 3.9). See
NAVIGATION_BROWSER_VERIFIER.md.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

TASK = "T05.008"

# The frozen normative profile.json, verbatim (2153 bytes; checked at import).
PROFILE_SHA256 = "6629304cf8ffcb5c9c889db61e2f95041b45e591b715d9f4cf5d4c573c8bfe97"
PROFILE_TEXT = r'''{
  "api_html": {
    "bytes": 5848,
    "replace_expression": "import('./' + scriptFile)",
    "sha256": "9a22f87113303bd16db27d577e30b0576c550ba22de886a1cec474d786665562"
  },
  "bundles": {
    "original": {
      "bytes": 13166284,
      "sha256": "80f4371cc8da2bb54432e46e7e34dfaf7acc56444b28c6fbc6a99c6ba22933ea"
    },
    "repaired": {
      "bytes": 13172839,
      "sha256": "6ba854cb67b1306cadb905b1b89a7a1eac98cd7e5c912196e6f87df41a5c4c2f"
    }
  },
  "element_ids": [
    "T05_008-cache-report",
    "T05_008-entry-status",
    "inspect-cache",
    "remove-verified-cache",
    "refresh-http-original",
    "refresh-http-repaired"
  ],
  "origin": "http://127.0.0.1:3338",
  "output_files": [
    "T05_008-cache.html",
    "T05_008-cache.mjs",
    "T05_008-original-entry.html",
    "T05_008-repaired-entry.html",
    "verification-manifest.json"
  ],
  "profile": "fixed-navigation-browser-verifier-v1",
  "schema": 1,
  "targets": [
    {
      "bytes": 67328,
      "path": "data/luafiles514/lua files/navigation/navi_map_krpri.lub",
      "sha256": "e7c8d566b5883df68d01830f0ce4ec385fc8ac084a1a8f6944bd517d89a046dc"
    },
    {
      "bytes": 396243,
      "path": "data/luafiles514/lua files/navigation/navi_mob_krpri.lub",
      "sha256": "02aeb90a6df4af8f2e4fc8adf5a88f70b5ac1c48e32373a7cba57439a776c3c7"
    },
    {
      "bytes": 1025994,
      "path": "data/luafiles514/lua files/navigation/navi_npc_krpri.lub",
      "sha256": "7b760b652d8ce5a6353811aa57d433848b056f6bdc99a3ddbb585f88bb44b528"
    },
    {
      "bytes": 594363,
      "path": "data/luafiles514/lua files/navigation/navi_link_krpri.lub",
      "sha256": "f6526637f8cfc8755b92fad9e496f7c97439715db34a6efd430dfb870b62ff10"
    },
    {
      "bytes": 1556072,
      "path": "data/luafiles514/lua files/navigation/navi_linkdistance_krpri.lub",
      "sha256": "26cea879a399a1362a02deecf0ef3b07c7d4bfcdf01938f08f98338e5f05c193"
    },
    {
      "bytes": 3840599,
      "path": "data/luafiles514/lua files/navigation/navi_npcdistance_krpri.lub",
      "sha256": "3e896b2ba29de46f40ab36e43917359b376612ef00b3b4c0e2eb0cc81cb95471"
    }
  ],
  "task": "T05.008"
}
'''

CACHE_HTML = "T05_008-cache.html"
CACHE_MODULE = "T05_008-cache.mjs"
ORIGINAL_ENTRY = "T05_008-original-entry.html"
REPAIRED_ENTRY = "T05_008-repaired-entry.html"
MANIFEST = "verification-manifest.json"
AUTHORED_MODULE = Path(__file__).resolve().parent / "navigation_browser_cache.mjs"
MODULE_CAP = 1 << 20
DIR_MODE = 0o700
FILE_MODE = 0o600

_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class VerifierError(Exception):
    """A refusal or failure with a bounded, path-free diagnosis."""


def canonical(value):
    """The one JSON serialization this tool writes."""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def sri(hex_digest):
    """Subresource-integrity value for a lowercase SHA-256 hex digest."""
    return "sha256-" + base64.b64encode(bytes.fromhex(hex_digest)).decode("ascii")


def _why(error):
    return error.strerror or type(error).__name__


def _load_profile():
    data = PROFILE_TEXT.encode("utf-8")
    if len(data) != 2153 or _sha(data) != PROFILE_SHA256:
        raise RuntimeError("embedded profile differs from the frozen profile.json")
    profile = json.loads(data)
    if canonical(profile) != data:
        raise RuntimeError("embedded profile is not canonical")
    expected = [CACHE_HTML, CACHE_MODULE, ORIGINAL_ENTRY, REPAIRED_ENTRY, MANIFEST]
    if profile["task"] != TASK or profile["schema"] != 1 or profile["output_files"] != expected:
        raise RuntimeError("embedded profile does not describe this generator")
    return profile


PROFILE = _load_profile()


# ------------------------------------------------------------- page sources

# The single replacement for import('./' + scriptFile). It is evaluated where
# that call was, inside loadApp after the bootstrap's own config merge, and
# yields a Promise so the original .then/.catch stays in force. The status
# record is created here because no other bootstrap byte may change.
ENTRY_EXPRESSION = """(function (scriptFile) {
                    // T05.008: load only the pinned Online.js, checked by browser-enforced SRI.
                    var ORIGIN = '@@ORIGIN@@';
                    var EXPECTED = '@@SHA256@@';
                    var INTEGRITY = '@@INTEGRITY@@';
                    var record = { task: 'T05.008', stage: '@@STAGE@@', state: 'pending', expected_sha256: EXPECTED, integrity: INTEGRITY, module_url: null, reason: null };
                    var node = document.getElementById('T05_008-entry-status');
                    if (!node) {
                        node = document.createElement('pre');
                        node.id = 'T05_008-entry-status';
                        node.setAttribute('style', 'position:fixed;left:0;bottom:0;z-index:100000;margin:0;padding:4px 6px;max-width:100%;white-space:pre-wrap;word-break:break-all;font:11px/1.3 monospace;color:#fff;background:rgba(0,0,0,0.85);pointer-events:none');
                        document.body.appendChild(node);
                    }
                    function show() { node.textContent = JSON.stringify(record); }
                    function refuse(reason) {
                        record.state = 'failed';
                        record.reason = reason;
                        show();
                        return Promise.reject(new Error('T05.008 entry refused: ' + reason));
                    }
                    if (window.T05_008_entryStarted) { return refuse('duplicate-entry'); }
                    window.T05_008_entryStarted = true;
                    show();
                    if (scriptFile !== 'Online.js') { return refuse('script-refused'); }
                    if (window.location.origin !== ORIGIN) { return refuse('origin-refused'); }
                    if (!window.crypto || typeof window.crypto.getRandomValues !== 'function') { return refuse('crypto-unavailable'); }
                    if (!('integrity' in HTMLScriptElement.prototype)) { return refuse('integrity-unsupported'); }
                    var url;
                    try {
                        var raw = new Uint8Array(16);
                        window.crypto.getRandomValues(raw);
                        var nonce = Array.prototype.map.call(raw, function (b) { return (b + 256).toString(16).slice(1); }).join('');
                        url = new URL('Online.js?t05_008_sha256=' + EXPECTED + '&t05_008_nonce=' + nonce, window.location.href);
                    } catch (e) {
                        return refuse('nonce-error');
                    }
                    if (url.origin !== ORIGIN) { return refuse('origin-refused'); }
                    record.module_url = url.href;
                    show();
                    return new Promise(function (resolve, reject) {
                        var done = false;
                        var script = document.createElement('script');
                        function finish(ok, reason) {
                            if (done) { return; }
                            done = true;
                            window.removeEventListener('error', onWindowError, true);
                            if (ok) {
                                record.state = 'loaded';
                                show();
                                resolve();
                            } else {
                                record.state = 'failed';
                                record.reason = reason;
                                show();
                                reject(new Error('T05.008 entry module ' + reason));
                            }
                        }
                        function onWindowError(event) {
                            if (event && event.filename === url.href) { finish(false, 'evaluation-error'); }
                        }
                        script.type = 'module';
                        script.integrity = INTEGRITY;
                        script.crossOrigin = 'anonymous';
                        script.addEventListener('load', function () { finish(true, null); });
                        script.addEventListener('error', function () { finish(false, 'load-or-integrity-error'); });
                        window.addEventListener('error', onWindowError, true);
                        script.src = url.href;
                        try {
                            document.head.appendChild(script);
                        } catch (e) {
                            finish(false, 'insert-error');
                        }
                    });
                })(scriptFile)"""

CACHE_PAGE = """<!DOCTYPE html>
<html lang="en" data-t05008="cache">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>T05.008 navigation cache verifier</title>
<style>
body { margin: 0; padding: 16px; font: 14px/1.4 system-ui, sans-serif; color: #111; background: #fff; }
button { margin: 0 8px 8px 0; padding: 6px 10px; font: inherit; }
pre { white-space: pre-wrap; word-break: break-all; padding: 8px; background: #f2f2f2; border: 1px solid #ccc; }
</style>
</head>
<body>
<h1>T05.008 navigation cache verifier</h1>
<p>Temporary local verifier for six fixed navigation cache copies on @@ORIGIN@@. Nothing runs automatically. Inspection is read-only; removal and HTTP refresh are separate explicit actions. Close every game tab and worker before any mutation.</p>
<p>
<button type="button" id="inspect-cache" disabled>Inspect six cache copies (read-only)</button>
<button type="button" id="remove-verified-cache" disabled>Remove verified cache copies</button>
<button type="button" id="refresh-http-original" disabled>Refresh HTTP: original server</button>
<button type="button" id="refresh-http-repaired" disabled>Refresh HTTP: repaired server</button>
</p>
<pre id="T05_008-cache-report">{"task": "T05.008", "state": "loading"}</pre>
<script>
(function () {
    // Load the controller only through browser-enforced SRI of its authored bytes.
    var ORIGIN = '@@ORIGIN@@';
    var EXPECTED = '@@SHA256@@';
    var INTEGRITY = '@@INTEGRITY@@';
    var report = document.getElementById('T05_008-cache-report');
    var done = false;
    function show(value) { report.textContent = JSON.stringify(value, null, 2); }
    function fail(code, url) {
        if (done) { return; }
        done = true;
        show({ task: 'T05.008', state: 'failed', code: code, module_url: url || null, expected_sha256: EXPECTED, integrity: INTEGRITY });
    }
    if (window.location.origin !== ORIGIN) { fail('origin-refused'); return; }
    if (!window.crypto || typeof window.crypto.getRandomValues !== 'function') { fail('crypto-unavailable'); return; }
    if (!('integrity' in HTMLScriptElement.prototype)) { fail('integrity-unsupported'); return; }
    var url;
    try {
        var raw = new Uint8Array(16);
        window.crypto.getRandomValues(raw);
        var nonce = Array.prototype.map.call(raw, function (b) { return (b + 256).toString(16).slice(1); }).join('');
        url = new URL('@@MODULE@@?t05_008_sha256=' + EXPECTED + '&t05_008_nonce=' + nonce, window.location.href);
    } catch (e) {
        fail('nonce-error');
        return;
    }
    if (url.origin !== ORIGIN) { fail('origin-refused'); return; }
    show({ task: 'T05.008', state: 'loading-module', module_url: url.href, expected_sha256: EXPECTED, integrity: INTEGRITY });
    var script = document.createElement('script');
    function onWindowError(event) {
        if (event && event.filename === url.href) { fail('module-evaluation-error', url.href); }
    }
    script.type = 'module';
    script.integrity = INTEGRITY;
    script.crossOrigin = 'anonymous';
    script.addEventListener('load', function () {
        window.removeEventListener('error', onWindowError, true);
        if (report.getAttribute('data-bound') !== '1') { fail('module-not-bound', url.href); }
        done = true;
    });
    script.addEventListener('error', function () {
        window.removeEventListener('error', onWindowError, true);
        fail('module-load-or-integrity-error', url.href);
    });
    window.addEventListener('error', onWindowError, true);
    script.src = url.href;
    document.head.appendChild(script);
})();
</script>
</body>
</html>
"""


def _fill(template, values):
    out = template
    for key, value in values.items():
        out = out.replace("@@" + key + "@@", value)
    if "@@" in out:
        raise VerifierError("internal error: unfilled template value")
    return out


def entry_expression(stage, profile=PROFILE):
    """The inline expression replacing the bootstrap's dynamic import."""
    bundle = profile["bundles"][stage]
    return _fill(ENTRY_EXPRESSION, {
        "ORIGIN": profile["origin"],
        "SHA256": bundle["sha256"],
        "INTEGRITY": sri(bundle["sha256"]),
        "STAGE": stage,
    })


def cache_page(module_bytes, profile=PROFILE):
    digest = _sha(module_bytes)
    return _fill(CACHE_PAGE, {
        "ORIGIN": profile["origin"],
        "SHA256": digest,
        "INTEGRITY": sri(digest),
        "MODULE": CACHE_MODULE,
    }).encode("utf-8")


def entry_page(api, stage, profile=PROFILE):
    """api with only the pinned import expression replaced."""
    marker = profile["api_html"]["replace_expression"].encode("ascii")
    if api.count(marker) != 1:
        raise VerifierError("API_HTML does not hold exactly one import expression")
    start = api.index(marker)
    end = start + len(marker)
    page = api[:start] + entry_expression(stage, profile).encode("utf-8") + api[end:]
    if not (page.startswith(api[:start]) and page.endswith(api[end:])):
        raise VerifierError("internal error: bootstrap prefix or suffix changed")
    return page


def cache_inline_script(page):
    """The one inline classic script of the generated cache page."""
    text = page.decode("utf-8")
    if text.count("<script>") != 1 or text.count("</script>") != 1:
        raise VerifierError("internal error: cache page must hold one inline script")
    return text.split("<script>", 1)[1].split("</script>", 1)[0]


def _check_inline(text, what):
    lowered = text.lower()
    for bad in ("</script", "<!--", "eval(", "new function", "blob:", "createobjecturl"):
        if bad in lowered:
            raise VerifierError("internal error: %s holds a forbidden token" % what)


def check_module(module_bytes, profile=PROFILE):
    """The authored module must carry the same fixed pins as the profile."""
    try:
        text = module_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise VerifierError("authored cache module is not UTF-8")
    # The entry-status ID belongs to the entry pages, not to this module.
    ids = [i for i in profile["element_ids"] if i != "T05_008-entry-status"]
    needles = [profile["origin"], profile["profile"]] + ids
    for target in profile["targets"]:
        needles += [target["path"], target["sha256"], str(target["bytes"])]
    for bundle in profile["bundles"].values():
        needles += [bundle["sha256"], str(bundle["bytes"])]
    for needle in needles:
        if needle not in text:
            raise VerifierError("authored cache module does not carry the fixed profile pins")


# ------------------------------------------------------------- input / output


def _read_regular(path, cap, what):
    """Read a regular non-link file with a bounded size; refuse specials."""
    try:
        st = os.lstat(path)
    except OSError as error:
        raise VerifierError("%s unavailable: %s" % (what, _why(error)))
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise VerifierError("%s is not a regular file" % what)
    try:
        fd = os.open(path, os.O_RDONLY | _O_CLOEXEC | _O_NOFOLLOW)
    except OSError as error:
        raise VerifierError("%s unavailable: %s" % (what, _why(error)))
    try:
        fst = os.fstat(fd)
        if not stat.S_ISREG(fst.st_mode) or (fst.st_dev, fst.st_ino) != (st.st_dev, st.st_ino):
            raise VerifierError("%s changed while opening" % what)
        if fst.st_size > cap:
            raise VerifierError("%s has the wrong size" % what)
        chunks = []
        total = 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            total += len(chunk)
            if total > cap:
                raise VerifierError("%s has the wrong size" % what)
            chunks.append(chunk)
    except OSError as error:
        os.close(fd)
        raise VerifierError("%s unreadable: %s" % (what, _why(error)))
    except BaseException:
        os.close(fd)
        raise
    try:
        os.close(fd)
    except OSError as error:
        raise VerifierError("%s unreadable: %s" % (what, _why(error)))
    return b"".join(chunks)


def read_api(path, profile=PROFILE):
    pin = profile["api_html"]
    data = _read_regular(path, pin["bytes"], "API_HTML")
    if len(data) != pin["bytes"] or _sha(data) != pin["sha256"]:
        raise VerifierError("API_HTML is not the pinned bootstrap")
    if data.count(pin["replace_expression"].encode("ascii")) != 1:
        raise VerifierError("API_HTML does not hold exactly one import expression")
    return data


def _check_output(path):
    if os.path.lexists(path):
        raise VerifierError("OUTPUT already exists")
    parent = os.path.dirname(os.path.abspath(path))
    try:
        st = os.stat(parent)
    except OSError as error:
        raise VerifierError("OUTPUT parent unavailable: %s" % _why(error))
    if not stat.S_ISDIR(st.st_mode):
        raise VerifierError("OUTPUT parent is not a directory")


def _write_file(directory_fd, name, data, created):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_CLOEXEC | _O_NOFOLLOW,
                 FILE_MODE, dir_fd=directory_fd)
    created.append(name)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise VerifierError("short write")
            view = view[written:]
        os.fchmod(fd, FILE_MODE)
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        raise
    os.close(fd)


def _write_tree(output, files):
    """Create OUTPUT and its files exclusively; manifest last."""
    try:
        os.mkdir(output, DIR_MODE)
    except OSError as error:
        raise VerifierError("cannot create OUTPUT: %s" % _why(error))
    created = []
    directory_fd = None
    try:
        directory_fd = os.open(output, os.O_RDONLY | _O_CLOEXEC | _O_NOFOLLOW)
        os.fchmod(directory_fd, DIR_MODE)
        for name, data in files:
            _write_file(directory_fd, name, data, created)
        os.fsync(directory_fd)
        if sorted(os.listdir(directory_fd)) != sorted(name for name, _ in files):
            raise VerifierError("OUTPUT holds unexpected entries")
    except (OSError, VerifierError) as error:
        # Remove only what this run created; never leave a usable partial tree.
        for name in created:
            try:
                os.unlink(name, dir_fd=directory_fd)
            except OSError:
                pass
        if directory_fd is not None:
            os.close(directory_fd)
            directory_fd = None
        try:
            os.rmdir(output)
        except OSError:
            pass
        reason = _why(error) if isinstance(error, OSError) else str(error)
        raise VerifierError("writing OUTPUT failed: %s" % reason)
    finally:
        if directory_fd is not None:
            os.close(directory_fd)


def build(api_path, output, profile=PROFILE, module_path=AUTHORED_MODULE):
    """Validate every input, then write the five files. Returns the manifest."""
    _check_output(output)
    api = read_api(api_path, profile)
    module = _read_regular(str(module_path), MODULE_CAP, "authored cache module")
    check_module(module, profile)
    cache_html = cache_page(module, profile)
    original = entry_page(api, "original", profile)
    repaired = entry_page(api, "repaired", profile)
    _check_inline(entry_expression("original", profile), "entry expression")
    _check_inline(cache_inline_script(cache_html), "cache page script")
    browser = {
        CACHE_HTML: cache_html,
        CACHE_MODULE: module,
        ORIGINAL_ENTRY: original,
        REPAIRED_ENTRY: repaired,
    }
    manifest = {
        "artifacts": {name: {"bytes": len(data), "sha256": _sha(data)} for name, data in browser.items()},
        "cache_module": {"bytes": len(module), "integrity": sri(_sha(module)), "sha256": _sha(module)},
        "entry_bundles": {
            stage: {"bytes": pin["bytes"], "integrity": sri(pin["sha256"]), "sha256": pin["sha256"]}
            for stage, pin in profile["bundles"].items()
        },
        "origin": profile["origin"],
        "profile": profile["profile"],
        "profile_sha256": PROFILE_SHA256,
        "schema": 1,
        "source_api_html": {"bytes": len(api), "sha256": _sha(api)},
        "task": TASK,
    }
    manifest_bytes = canonical(manifest)
    _check_output(output)
    _write_tree(output, list(browser.items()) + [(MANIFEST, manifest_bytes)])
    return manifest, _sha(manifest_bytes)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or any(arg.startswith("-") for arg in args):
        sys.stderr.write("usage: navigation_browser_verifier.py API_HTML OUTPUT\n")
        return 2
    try:
        _, manifest_sha = build(args[0], args[1])
    except VerifierError as error:
        sys.stderr.write("T05.008 refused: %s\n" % error)
        return 1
    sys.stdout.write(json.dumps({
        "files": 5,
        "manifest_sha256": manifest_sha,
        "output": os.path.basename(os.path.abspath(args[1])),
        "state": "generated",
        "task": TASK,
    }, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
