#!/usr/bin/env python3
"""Focused checks for quest_true_text_mod.py (T10.008).

    python3 -I -B tools/renewal/test_quest_true_text_mod.py --source FILE --workdir NEW_DIR

FILE must be the actual retained OngoingQuestInfoList_True.lub: a missing or
different file fails, it is never skipped or replaced by a synthetic positive.
NEW_DIR must not exist; every fixture and output is created under it (0700
directories, 0600 files). The FIFO and symlinks a control creates are removed
by exact name afterwards, so only ordinary files remain. Each control drives
the production generator, in-process or as one bounded CLI child, and checks
that refusals and failures leave existing state unchanged.
Standard library only (Python 3.9).
"""

import argparse
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import signal
import stat
import subprocess
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
GENERATOR = os.path.join(HERE, "quest_true_text_mod.py")
PROFILE = os.path.join(HERE, "..", "..", "docs", "project", "fixtures", "T10.008-profile.json")
CHILD_TIMEOUT = 60
STREAM_LIMIT = 65536

spec = importlib.util.spec_from_file_location("quest_true_text_mod", GENERATOR)
gm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gm)

SOURCE = None
WORK = None
with open(PROFILE, "rb") as f:
    PROFILE_DATA = json.load(f)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    with open(path, "rb") as f:
        return f.read()


def snapshot(path):
    """Type, mode and content of everything at and under `path`, no links followed."""
    out = {}

    def visit(p, rel):
        try:
            st = os.lstat(p)
        except FileNotFoundError:
            out[rel] = None
            return
        mode = stat.S_IMODE(st.st_mode)
        if stat.S_ISLNK(st.st_mode):
            out[rel] = ("link", os.readlink(p))
        elif stat.S_ISREG(st.st_mode):
            out[rel] = ("file", mode, st.st_size, st.st_mtime_ns, sha256(read(p)))
        elif stat.S_ISDIR(st.st_mode):
            out[rel] = ("dir", mode)
            for name in sorted(os.listdir(p)):
                visit(os.path.join(p, name), rel + "/" + name)
        else:
            out[rel] = ("other", stat.S_IFMT(st.st_mode), mode)

    visit(path, ".")
    return out


def tree(path):
    """Relative path -> (kind, mode) under `path`, the root excluded."""
    found = {}
    for top, dirs, files in os.walk(path):
        for name in dirs + files:
            p = os.path.join(top, name)
            st = os.lstat(p)
            kind = "dir" if stat.S_ISDIR(st.st_mode) else "file" if stat.S_ISREG(st.st_mode) else "other"
            found[os.path.relpath(p, path).replace(os.sep, "/")] = (kind, stat.S_IMODE(st.st_mode))
    return found


def run_cli(*args):
    """One timed CLI child; check complete stream lengths after capture."""
    proc = subprocess.run(
        [sys.executable, "-I", "-B", GENERATOR] + list(args),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=CHILD_TIMEOUT,
    )
    if len(proc.stdout) > STREAM_LIMIT or len(proc.stderr) > STREAM_LIMIT:
        raise AssertionError("CLI output exceeded the post-capture limit")
    return proc.returncode, proc.stdout, proc.stderr


def run_main(*args):
    """The production main() in-process, with captured bounded streams."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = gm.main(list(args))
    if len(out.getvalue()) > STREAM_LIMIT or len(err.getvalue()) > STREAM_LIMIT:
        raise AssertionError("main output exceeded the post-capture limit")
    return rc, out.getvalue(), err.getvalue()


@contextlib.contextmanager
def deadline(seconds):
    def expire(signum, frame):
        raise TimeoutError("control blocked for %ds" % seconds)

    old = signal.signal(signal.SIGALRM, expire)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


_counter = [0]


def fresh(label):
    _counter[0] += 1
    path = os.path.join(WORK, "%02d-%s" % (_counter[0], label))
    os.mkdir(path, 0o700)
    return path


def write(path, data):
    with open(path, "xb") as f:
        f.write(data)


class Base(unittest.TestCase):
    def setUp(self):
        self.source_before = snapshot(SOURCE)

    def tearDown(self):
        self.assertEqual(snapshot(SOURCE), self.source_before, "source changed")

    def assert_refused(self, rc, err, case_dir, before, output):
        self.assertEqual(rc, 2, err)
        self.assertIn("refused:", str(err))
        self.assertEqual(snapshot(case_dir), before, "refusal changed existing state")
        if before.get("./" + os.path.basename(output)) is None:
            self.assertFalse(os.path.lexists(output), "refusal created output")

    def assert_no_receipt(self, rc, err, out):
        self.assertEqual(rc, 1, err)
        self.assertIn("incomplete output retained for review", err)
        self.assertFalse(os.path.lexists(os.path.join(out, gm.RESULT_NAME)))
        self.assertTrue(os.path.isdir(out))


class A_Positive(Base):
    """Real retained input through the CLI; exact output, schema and modes."""

    def test_cli_positive_output(self):
        source = read(SOURCE)
        self.assertEqual(len(source), PROFILE_DATA["input"]["bytes"])
        self.assertEqual(sha256(source), PROFILE_DATA["input"]["sha256"])
        out = os.path.join(fresh("positive-cli"), "out")
        rc, stdout, stderr = run_cli("--source", SOURCE, "--output", out)
        self.assertEqual(rc, 0, stderr)
        slug = PROFILE_DATA["mod_manifest"]["name"]
        table_rel = slug + "/System/OngoingQuestInfoList-" + slug + ".lub"
        self.assertEqual(stat.S_IMODE(os.lstat(out).st_mode), 0o700)
        self.assertEqual(tree(out), {
            slug: ("dir", 0o700),
            slug + "/System": ("dir", 0o700),
            slug + "/mod.json": ("file", 0o600),
            table_rel: ("file", 0o600),
            "RESULT.json": ("file", 0o600),
        })
        manifest = read(os.path.join(out, slug, "mod.json"))
        self.assertEqual(json.loads(manifest), PROFILE_DATA["mod_manifest"])
        table = read(os.path.join(out, *table_rel.split("/")))
        self.assertEqual(table, source)
        receipt = json.loads(read(os.path.join(out, "RESULT.json")))
        want = PROFILE_DATA["receipt"]
        self.assertEqual(list(receipt), ["schema", "status", "slug", "input", "files"])
        self.assertEqual(receipt["schema"], want["schema"])
        self.assertEqual(receipt["status"], want["status"])
        self.assertEqual(receipt["slug"], want["slug"])
        self.assertEqual(receipt["input"], want["input"])
        self.assertEqual(receipt["files"], [
            {"path": slug + "/mod.json", "bytes": len(manifest), "sha256": sha256(manifest)},
            {"path": table_rel, "bytes": len(table), "sha256": sha256(table)},
        ])
        self.assertEqual(stdout, b"", "RESULT.json is the success channel")
        A_Positive.output = out


class B_Deterministic(Base):
    def test_ordinary_parent_traversal_remains_valid(self):
        case = fresh("ordinary-parent-traversal")
        inner = os.path.join(case, "inner")
        os.mkdir(inner)
        write(os.path.join(case, "table.lub"), read(SOURCE))
        source = os.path.join(inner, "..", "table.lub")
        output = os.path.join(inner, "..", "out")
        rc, stdout, stderr = run_main("--source", source, "--output", output)
        self.assertEqual(rc, 0, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(read(os.path.join(output, gm.TABLE_PATH)), read(SOURCE))
        self.assertEqual(json.loads(read(os.path.join(output, gm.RESULT_NAME)))["status"], "ok")

    def test_second_fresh_run_identical(self):
        first = getattr(A_Positive, "output", None)
        self.assertIsNotNone(first, "positive CLI run did not complete")
        out = os.path.join(fresh("positive-second"), "out")
        rc, stdout, stderr = run_main("--source", SOURCE, "--output", out)
        self.assertEqual(rc, 0, stderr)
        for rel in (gm.MANIFEST_PATH, gm.TABLE_PATH):
            self.assertEqual(read(os.path.join(out, rel)), read(os.path.join(first, rel)), rel)
        self.assertEqual(read(os.path.join(out, "RESULT.json")), read(os.path.join(first, "RESULT.json")))

    def test_generator_is_byte_copy_only(self):
        text = read(GENERATOR).decode("utf-8")
        imports = set()
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
        self.assertEqual(imports, {"argparse", "hashlib", "json", "os", "stat", "sys"})
        for token in ("decode(", "Config.local", "customQuestInfo", "servers", "eval(", "exec(",
                      "rmtree", "os.remove", "os.unlink", "os.rmdir", "--slug", "/Users/"):
            self.assertNotIn(token, text, token)


class C_SourceRefusals(Base):
    def refuse_source(self, label, make_source, cli=False):
        case = fresh(label)
        source = make_source(case)
        out = os.path.join(case, "out")
        before = snapshot(case)
        with deadline(30):
            rc, _, err = (run_cli if cli else run_main)("--source", source, "--output", out)
        self.assert_refused(rc, err if isinstance(err, str) else err.decode(), case, before, out)
        return case, source

    def test_wrong_size_short_and_long(self):
        data = read(SOURCE)
        for label, body in (("short", data[:-1]), ("long", data + b"\n")):
            self.refuse_source("size-" + label, lambda c, b=body: (write(os.path.join(c, "t.lub"), b), os.path.join(c, "t.lub"))[1])

    def test_same_size_wrong_hash(self):
        data = bytearray(read(SOURCE))
        data[-1] ^= 0xFF
        self.refuse_source("hash", lambda c: (write(os.path.join(c, "t.lub"), bytes(data)), os.path.join(c, "t.lub"))[1])

    def test_missing_source(self):
        self.refuse_source("missing", lambda c: os.path.join(c, "absent.lub"))

    def test_directory_source(self):
        self.refuse_source("dir", lambda c: (os.mkdir(os.path.join(c, "d.lub")), os.path.join(c, "d.lub"))[1])

    def test_fifo_source_does_not_block(self):
        for cli in (False, True):
            def make(c):
                os.mkfifo(os.path.join(c, "f.lub"), 0o600)
                return os.path.join(c, "f.lub")
            _, fifo = self.refuse_source("fifo-cli" if cli else "fifo", make, cli=cli)
            os.unlink(fifo)

    def test_symlink_source(self):
        def make(c):
            os.symlink(SOURCE, os.path.join(c, "link.lub"))
            return os.path.join(c, "link.lub")
        _, link = self.refuse_source("symlink", make)
        os.unlink(link)

    def test_symlink_source_component(self):
        holder = fresh("source-holder")
        write(os.path.join(holder, "t.lub"), read(SOURCE))

        def make(c):
            os.symlink(holder, os.path.join(c, "via"))
            return os.path.join(c, "via", "t.lub")
        case, path = self.refuse_source("symlink-component", make)
        os.unlink(os.path.join(case, "via"))

    def test_symlink_source_component_before_parent_traversal(self):
        def make(c):
            real = os.path.join(c, "real")
            os.mkdir(real)
            os.mkdir(os.path.join(real, "inner"))
            # Keep both lexical and traversed paths valid, so neither can hide
            # the component-validation defect behind a missing-file refusal.
            write(os.path.join(c, "table.lub"), read(SOURCE))
            write(os.path.join(real, "table.lub"), read(SOURCE))
            os.symlink(os.path.join(real, "inner"), os.path.join(c, "via"))
            return os.path.join(c, "via", "..", "table.lub")
        case, _ = self.refuse_source("source-parent-traversal", make)
        os.unlink(os.path.join(case, "via"))


class D_OutputRefusalsAndFailures(Base):
    def refuse_output(self, label, make_output):
        case = fresh(label)
        out = make_output(case)
        before = snapshot(case)
        rc, _, err = run_main("--source", SOURCE, "--output", out)
        self.assert_refused(rc, err, case, before, out)
        return case

    def test_existing_directory(self):
        def make(c):
            os.mkdir(os.path.join(c, "out"))
            write(os.path.join(c, "out", "keep.txt"), b"keep\n")
            return os.path.join(c, "out")
        self.refuse_output("exists-dir", make)

    def test_existing_file(self):
        def make(c):
            write(os.path.join(c, "out"), b"keep\n")
            return os.path.join(c, "out")
        self.refuse_output("exists-file", make)

    def test_existing_symlink(self):
        def make(c):
            os.mkdir(os.path.join(c, "target"))
            write(os.path.join(c, "target", "keep.txt"), b"keep\n")
            os.symlink(os.path.join(c, "target"), os.path.join(c, "out"))
            return os.path.join(c, "out")
        case = self.refuse_output("exists-symlink", make)
        os.unlink(os.path.join(case, "out"))

    def test_dangling_symlink(self):
        def make(c):
            os.symlink(os.path.join(c, "nowhere"), os.path.join(c, "out"))
            return os.path.join(c, "out")
        case = self.refuse_output("dangling-symlink", make)
        self.assertFalse(os.path.lexists(os.path.join(case, "nowhere")))
        os.unlink(os.path.join(case, "out"))

    def test_symlink_output_component(self):
        def make(c):
            os.mkdir(os.path.join(c, "real"))
            os.symlink(os.path.join(c, "real"), os.path.join(c, "via"))
            return os.path.join(c, "via", "out")
        case = self.refuse_output("symlink-component", make)
        self.assertEqual(os.listdir(os.path.join(case, "real")), [])
        os.unlink(os.path.join(case, "via"))

    def test_symlink_output_component_before_parent_traversal(self):
        def make(c):
            os.mkdir(os.path.join(c, "real"))
            os.mkdir(os.path.join(c, "real", "inner"))
            os.symlink(os.path.join(c, "real", "inner"), os.path.join(c, "via"))
            return os.path.join(c, "via", "..", "out")
        case = self.refuse_output("output-parent-traversal", make)
        self.assertFalse(os.path.lexists(os.path.join(case, "out")))
        self.assertFalse(os.path.lexists(os.path.join(case, "real", "out")))
        os.unlink(os.path.join(case, "via"))

    def test_missing_parent(self):
        self.refuse_output("missing-parent", lambda c: os.path.join(c, "absent", "out"))

    def test_parent_is_file(self):
        def make(c):
            write(os.path.join(c, "plain"), b"keep\n")
            return os.path.join(c, "plain", "out")
        self.refuse_output("parent-file", make)

    def test_output_created_after_check(self):
        real_check = gm.check_output

        def racing(path):
            real_check(path)
            os.mkdir(path)
            write(os.path.join(path, "keep.txt"), b"keep\n")

        case = fresh("race")
        out = os.path.join(case, "out")
        with mock.patch.object(gm, "check_output", racing):
            rc, _, err = run_main("--source", SOURCE, "--output", out)
        self.assertEqual(rc, 2, err)
        self.assertEqual(os.listdir(out), ["keep.txt"])
        self.assertEqual(read(os.path.join(out, "keep.txt")), b"keep\n")

    def test_induced_write_failure(self):
        real_write = os.write

        def failing(fd, data):
            if len(data) > 1 << 19:
                real_write(fd, bytes(data[:4096]))
                raise OSError(28, "induced: no space left on device")
            return real_write(fd, data)

        out = os.path.join(fresh("write-failure"), "out")
        with mock.patch.object(gm.os, "write", failing):
            rc, _, err = run_main("--source", SOURCE, "--output", out)
        self.assert_no_receipt(rc, err, out)
        self.assertEqual(os.path.getsize(os.path.join(out, gm.TABLE_PATH)), 4096)

    def test_zero_write_progress_refuses_without_hanging(self):
        out = os.path.join(fresh("zero-write"), "out")
        with deadline(5), mock.patch.object(gm.os, "write", return_value=0):
            rc, _, err = run_main("--source", SOURCE, "--output", out)
        self.assert_no_receipt(rc, err, out)

    def test_chmod_failure_after_root_creation_reports_incomplete_output(self):
        out = os.path.join(fresh("chmod-failure"), "out")
        real_chmod = os.chmod

        def failing(path, mode):
            if path == out:
                raise OSError(5, "induced post-mkdir chmod failure")
            return real_chmod(path, mode)

        with mock.patch.object(gm.os, "chmod", failing):
            rc, _, err = run_main("--source", SOURCE, "--output", out)
        self.assert_no_receipt(rc, err, out)
        self.assertIn(out, err)
        self.assertNotIn("before creating", err)

    def test_receipt_close_failure_does_not_publish_success(self):
        out = os.path.join(fresh("receipt-close-failure"), "out")
        real_open, real_close = os.open, os.close
        target, injected = [None], [False]

        def opening(path, flags, *args, **kwargs):
            fd = real_open(path, flags, *args, **kwargs)
            if flags & os.O_WRONLY and os.path.basename(path) == gm.PARTIAL_NAME:
                target[0] = fd
            return fd

        def closing(fd):
            real_close(fd)
            if fd == target[0] and not injected[0]:
                target[0], injected[0] = None, True
                raise OSError(5, "induced receipt close failure")

        with mock.patch.object(gm.os, "open", opening), mock.patch.object(gm.os, "close", closing):
            rc, _, err = run_main("--source", SOURCE, "--output", out)
        self.assertTrue(injected[0])
        self.assert_no_receipt(rc, err, out)

    def test_success_does_not_require_stdout(self):
        class Unavailable(io.StringIO):
            def write(self, _text):
                raise OSError(5, "stdout unavailable")

        out = os.path.join(fresh("stdout-unavailable"), "out")
        err = io.StringIO()
        with contextlib.redirect_stdout(Unavailable()), contextlib.redirect_stderr(err):
            rc = gm.main(["--source", SOURCE, "--output", out])
        self.assertEqual(rc, 0, err.getvalue())
        self.assertEqual(json.loads(read(os.path.join(out, gm.RESULT_NAME)))["status"], "ok")

    def induced_readback(self, label, target):
        real_read = gm.read_bounded

        def corrupt(path, limit):
            data = real_read(path, limit)
            if path.endswith(target):
                data = data[:-1] + bytes([data[-1] ^ 0xFF])
            return data

        out = os.path.join(fresh(label), "out")
        with mock.patch.object(gm, "read_bounded", corrupt):
            rc, _, err = run_main("--source", SOURCE, "--output", out)
        self.assert_no_receipt(rc, err, out)
        self.assertIn("readback", err)
        return out

    def test_induced_table_readback_failure(self):
        self.induced_readback("readback-table", os.path.basename(gm.TABLE_PATH))

    def test_induced_receipt_readback_failure(self):
        out = self.induced_readback("readback-receipt", gm.PARTIAL_NAME)
        self.assertTrue(os.path.isfile(os.path.join(out, gm.PARTIAL_NAME)))


def private_tree_problems(path):
    problems = []
    for rel, (kind, mode) in sorted(tree(path).items()):
        if (kind, mode) not in (("dir", 0o700), ("file", 0o600)):
            problems.append("%s %s %o" % (rel, kind, mode))
    return problems


def main():
    global SOURCE, WORK
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source", required=True)
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args()
    SOURCE = os.path.abspath(args.source)
    WORK = os.path.abspath(args.workdir)
    if not os.path.isfile(SOURCE) or os.path.islink(SOURCE):
        print("FAIL: actual retained True source is missing or not an ordinary file", file=sys.stderr)
        return 1
    os.umask(0o077)
    os.mkdir(WORK, 0o700)
    os.chmod(WORK, 0o700)

    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    for case in (A_Positive, B_Deterministic, C_SourceRefusals, D_OutputRefusalsAndFailures):
        suite.addTests(loader.loadTestsFromTestCase(case))
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)

    problems = private_tree_problems(WORK)
    summary = {
        "run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "private_tree_problems": problems,
        "positive_outputs": [os.path.relpath(p, WORK) for p in (getattr(A_Positive, "output", None),) if p],
    }
    with open(os.path.join(WORK, "TEST_SUMMARY.json"), "x") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")
    print(json.dumps(summary, indent=2))
    ok = result.wasSuccessful() and not result.skipped and not problems
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
