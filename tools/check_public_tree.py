#!/usr/bin/env python3
"""Check indexed paths against this repository's source-only publishing policy.

Works before the first commit and in a CI checkout. This is a path guard, not a
secret-content scanner or a copyright classifier.
"""

from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


EXCLUDED_ROOTS = (
    "assets/reference-ro/",
    "tools/character-lab/assets/",
    "tools/character-lab/qa/",
    "docs/character-lab/releases/",
)
ALLOWED_PATHS = {
    "assets/reference-ro/README.md",
    "tools/character-lab/assets/README.md",
}
EXCLUDED_DIRECTORIES = {
    ".godot", ".tools", ".cache", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules", ".venv", "venv",
    "logs", "exports", ".ssh", ".aws", ".azure", ".gnupg",
}
EXCLUDED_SUFFIXES = {
    # Media and archives stay local, including generated or reference artwork.
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".tga",
    ".tif", ".tiff", ".ico", ".svg", ".svgz", ".psd", ".ase", ".aseprite",
    ".apng", ".heic", ".heif", ".jxl", ".dds", ".exr", ".hdr",
    ".mp4", ".m4v", ".mov", ".webm", ".avi", ".mkv", ".mpg", ".mpeg",
    ".flv", ".wmv", ".3gp", ".m2ts",
    ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".opus",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tgz",
    ".zst", ".lz", ".lzma", ".cab", ".iso",
    # Native RO assets, generated imports, binary exports, and local key files.
    ".act", ".spr", ".grf", ".gpf", ".gat", ".gnd", ".rsw", ".rsm",
    ".rsm2", ".str", ".pal", ".lub", ".import", ".ctex", ".stex",
    ".glb", ".gltf", ".fbx", ".blend", ".obj", ".pck", ".bin",
    ".exe", ".dll", ".so", ".dylib", ".dmg", ".app", ".apk", ".ipa",
    ".pyc", ".pyo", ".log", ".pem", ".key", ".p12", ".pfx", ".keystore",
}
SENSITIVE_NAME = re.compile(
    r"^(?:credentials?|secrets?|tokens?|api[-_]?keys?|service[-_]?account)"
    r"(?:[._-].*)?$",
    re.IGNORECASE,
)


def rejection_reason(path):
    """Return the first policy violation for a tracked path, if any."""
    if path in ALLOWED_PATHS:
        return None
    lowered = path.lower()
    if lowered.startswith(EXCLUDED_ROOTS):
        return "local-only asset or evidence directory"
    parts = PurePosixPath(lowered).parts
    if any(part in EXCLUDED_DIRECTORIES for part in parts):
        return "local tool, cache, log, export, or credential directory"
    name = parts[-1]
    if name != ".env.example" and (name == ".env" or name.startswith(".env.")):
        return "environment file"
    if name in {".ds_store", ".lock", ".netrc", ".npmrc", ".pypirc", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}:
        return "local configuration or key file"
    if SENSITIVE_NAME.match(name):
        return "credential or secret filename"
    if PurePosixPath(lowered).suffix in EXCLUDED_SUFFIXES:
        return "media, archive, native binary, cache, or key extension"
    return None


def main():
    try:
        result = subprocess.run(
            ["git", "ls-files", "--full-name", "-z"],
            cwd=Path(__file__).resolve().parents[1],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        print("Public tree check failed: cannot read the Git index.", file=sys.stderr)
        return 2
    paths = [path.decode("utf-8", errors="surrogateescape")
             for path in result.stdout.split(b"\0") if path]
    violations = [(path, rejection_reason(path)) for path in paths]
    violations = [(path, reason) for path, reason in violations if reason]
    if violations:
        print(f"Public tree check failed: {len(violations)} excluded indexed paths.", file=sys.stderr)
        for path, reason in violations[:20]:
            print(f"  {ascii(path)}: {reason}", file=sys.stderr)
        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more.", file=sys.stderr)
        return 1
    print(f"Public tree check passed: {len(paths)} indexed paths.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
