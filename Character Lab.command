#!/bin/zsh
set -e
LAB_DIR="${0:A:h}/tools/character-lab"
if ! command -v python3 >/dev/null 2>&1; then
  print 'Python 3 is required to start Character Lab.'
  exit 1
fi
exec python3 - "$LAB_DIR" <<'PY'
import functools
import http.server
import json
import pathlib
import sys
import urllib.error
import urllib.request

root = pathlib.Path(sys.argv[1])
address = "http://127.0.0.1:8767"
if not (root / "index.html").is_file():
    sys.exit("Character Lab files are missing from tools/character-lab.")

# Reuse a Character Lab already served either directly or from the project root.
for path in ("/", "/tools/character-lab/"):
    try:
        with urllib.request.urlopen(address + path, timeout=1) as response:
            page = response.read(131072).decode("utf-8", errors="replace")
        if 'id="original-canvas"' not in page or "Character Atelier" not in page:
            continue
        with urllib.request.urlopen(address + path + "assets/manifest.json", timeout=1) as response:
            manifest = json.load(response)
        if manifest.get("schema") == "character-atelier-assets/1":
            print("Character Lab is already running. Open this address in your browser:")
            print(address + path, flush=True)
            sys.exit(0)
    except (OSError, ValueError, urllib.error.URLError):
        pass

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
try:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 8767), handler)
except OSError as error:
    sys.exit("Could not start Character Lab on port 8767: " + str(error))
print("Character Lab is ready. Open this address in your browser:")
print(address + "/")
print("Keep this Terminal window open. Press Control-C to stop.", flush=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nCharacter Lab stopped.")
finally:
    server.server_close()
PY
