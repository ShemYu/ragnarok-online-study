#!/usr/bin/env python3
"""Parse tracked Python and JavaScript without importing or executing them.

Uses the current Git index as the file inventory and reads working-tree bytes.
Private assets and runtime tests are outside this check.
"""

import ast
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.py", "*.js", "*.mjs", "*.cjs"],
        cwd=root, check=True, stdout=subprocess.PIPE,
    )
    paths = [root / name.decode("utf-8", errors="surrogateescape")
             for name in result.stdout.split(b"\0") if name]
    counts = {"Python": 0, "JavaScript": 0}
    failed = False
    for path in paths:
        relative = path.relative_to(root)
        try:
            if path.suffix == ".py":
                ast.parse(path.read_bytes(), filename=str(relative))
                counts["Python"] += 1
            else:
                parsed = subprocess.run(
                    ["node", "--check", str(path)], cwd=root,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                if parsed.returncode:
                    print(parsed.stderr, file=sys.stderr, end="")
                    failed = True
                counts["JavaScript"] += 1
        except (OSError, SyntaxError, ValueError) as error:
            print(f"{relative}: {error}", file=sys.stderr)
            failed = True
    print("Syntax {}: {} Python, {} JavaScript files. No code executed.".format(
        "failed" if failed else "passed", counts["Python"], counts["JavaScript"],
    ))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
