//! Optional five-path archive list for a later stack integration.
//!
//! `state/asset-archives.list` is the entire ordered archive vector when it
//! exists. Absence leaves the caller's legacy slots untouched. The file is
//! only read: this module creates no input, output, or archive body.

use std::fs::{self, File};
use std::io::{ErrorKind, Read};
use std::path::{Path, PathBuf};

const MANIFEST_NAME: &str = "asset-archives.list";
const ENTRY_COUNT: usize = 5;
const MANIFEST_CAP: u64 = 65_536;

#[cfg(test)]
std::thread_local! {
    static AFTER_OPEN_HOOK: std::cell::Cell<Option<fn(&Path)>> = const { std::cell::Cell::new(None) };
}

#[cfg(test)]
fn observe_open(path: &Path) {
    AFTER_OPEN_HOOK.with(|hook| {
        if let Some(callback) = hook.get() {
            callback(path);
        }
    });
}

#[cfg(not(test))]
fn observe_open(_path: &Path) {}

#[cfg(test)]
struct HookGuard;

#[cfg(test)]
impl Drop for HookGuard {
    fn drop(&mut self) {
        AFTER_OPEN_HOOK.with(|hook| hook.set(None));
    }
}

/// Install a callback that runs after the manifest's opened identity matches
/// and before its bytes are read. The guard removes it on drop, including
/// after a panic. This is the deterministic read-time seam; it is not a
/// general race harness.
#[cfg(test)]
fn install_after_open_hook(callback: fn(&Path)) -> HookGuard {
    AFTER_OPEN_HOOK.with(|hook| hook.set(Some(callback)));
    HookGuard
}

#[derive(Clone, Copy, PartialEq, Eq)]
struct Identity {
    dev: u64,
    ino: u64,
    nlink: u64,
    len: u64,
    mtime: i64,
    mtime_nsec: i64,
}

#[cfg(unix)]
fn identity_of(meta: &fs::Metadata) -> Identity {
    use std::os::unix::fs::MetadataExt;
    Identity {
        dev: meta.dev(),
        ino: meta.ino(),
        nlink: meta.nlink(),
        len: meta.len(),
        mtime: meta.mtime(),
        mtime_nsec: meta.mtime_nsec(),
    }
}

fn same_file(left: Identity, right: Identity) -> bool {
    left.dev == right.dev && left.ino == right.ino && left.nlink == right.nlink && left.len == right.len
}

fn unchanged(left: Identity, right: Identity) -> bool {
    same_file(left, right) && left.mtime == right.mtime && left.mtime_nsec == right.mtime_nsec
}

/// Read `state/asset-archives.list`.
///
/// `Ok(None)` means the list is absent, including when
/// `optional_archive_slots_present` is true. `Ok(Some)` is the canonical
/// archive vector in list order. `Err` is every present-list failure,
/// including a present list while optional archive slots are also set.
pub fn read_ordered_archives(
    state: &std::path::Path,
    data_anchor: &std::path::Path,
    optional_archive_slots_present: bool,
) -> Result<Option<Vec<std::path::PathBuf>>, String> {
    #[cfg(not(unix))]
    {
        let _ = (state, data_anchor, optional_archive_slots_present);
        return Err(
            "platform-unsupported: opened-file identity requires the admitted unix host".into(),
        );
    }
    #[cfg(unix)]
    {
        let manifest = state.join(MANIFEST_NAME);
        match fs::symlink_metadata(&manifest) {
            Err(err) if err.kind() == ErrorKind::NotFound => Ok(None),
            Err(err) => Err(format!("manifest-io: {err}")),
            Ok(_) if optional_archive_slots_present => Err(
                "optional-slot-conflict: asset-archives.list is present and optional archive slots are present"
                    .into(),
            ),
            Ok(_) => read_present_manifest(&manifest, data_anchor).map(Some),
        }
    }
}

#[cfg(unix)]
fn read_present_manifest(manifest: &Path, data_anchor: &Path) -> Result<Vec<PathBuf>, String> {
    let before_meta = fs::symlink_metadata(manifest).map_err(|err| format!("manifest-io: {err}"))?;
    classify_static(&before_meta)?;
    let before = identity_of(&before_meta);

    let mut file = File::open(manifest).map_err(|err| format!("manifest-unreadable: {err}"))?;
    let opened_meta = file.metadata().map_err(|err| format!("manifest-io: {err}"))?;
    let opened = identity_of(&opened_meta);
    let path_open_meta = fs::symlink_metadata(manifest).map_err(|err| format!("manifest-identity-changed: {err}"))?;
    let path_open = identity_of(&path_open_meta);
    if path_open_meta.file_type().is_symlink()
        || !opened_meta.file_type().is_file()
        || !unchanged(before, opened)
        || !unchanged(opened, path_open)
    {
        return Err(
            "manifest-identity-changed: opened descriptor does not match asset-archives.list".into(),
        );
    }

    // Test-only mutation point. Production builds call an empty function.
    observe_open(manifest);

    let bytes = read_bounded(&mut file, before.len)?;
    let after_meta = file.metadata().map_err(|err| format!("manifest-io: {err}"))?;
    let after = identity_of(&after_meta);
    let path_after_meta = fs::symlink_metadata(manifest).map_err(|err| format!("manifest-identity-changed: {err}"))?;
    let path_after = identity_of(&path_after_meta);
    if path_after_meta.file_type().is_symlink()
        || !path_after_meta.file_type().is_file()
        || !unchanged(opened, after)
        || !unchanged(opened, path_after)
        || bytes.len() as u64 != opened.len
    {
        return Err("manifest-identity-changed: asset-archives.list changed during read".into());
    }

    let lines = parse_manifest(&bytes)?;
    let mut admitted = Vec::with_capacity(ENTRY_COUNT);
    for line in lines {
        admitted.push(admit_entry(&line)?);
    }
    reject_duplicate_paths(&admitted)?;
    require_anchor_once(&admitted, data_anchor)?;
    Ok(admitted)
}

#[cfg(unix)]
fn classify_static(meta: &fs::Metadata) -> Result<(), String> {
    let kind = meta.file_type();
    if kind.is_symlink() {
        return Err("manifest-symlink: asset-archives.list is a symlink".into());
    }
    if !kind.is_file() {
        return Err("manifest-nonregular: asset-archives.list is not a regular file".into());
    }
    let id = identity_of(meta);
    if id.nlink != 1 {
        return Err(format!("manifest-hardlink: link count {}", id.nlink));
    }
    if id.len > MANIFEST_CAP {
        return Err(format!("manifest-over-cap: {} bytes", id.len));
    }
    Ok(())
}

#[cfg(unix)]
fn read_bounded(file: &mut File, declared: u64) -> Result<Vec<u8>, String> {
    let need = usize::try_from(declared).map_err(|_| format!("manifest-over-cap: {declared} bytes"))?;
    let mut bytes = vec![0_u8; need];
    if need > 0 {
        match file.read_exact(&mut bytes) {
            Ok(()) => {}
            Err(err) if err.kind() == ErrorKind::UnexpectedEof => {
                return Err("manifest-identity-changed: short read".into());
            }
            Err(err) => return Err(format!("manifest-unreadable: {err}")),
        }
    }
    let mut extra = [0_u8; 1];
    match file.read(&mut extra) {
        Ok(0) => Ok(bytes),
        Ok(_) => Err("manifest-identity-changed: asset-archives.list grew during read".into()),
        Err(err) => Err(format!("manifest-unreadable: {err}")),
    }
}

fn parse_manifest(bytes: &[u8]) -> Result<Vec<String>, String> {
    if bytes.contains(&0) {
        return Err("grammar-nul: NUL is not allowed".into());
    }
    if bytes.contains(&b'\r') {
        return Err("grammar-cr: CR is not allowed".into());
    }
    let text = std::str::from_utf8(bytes).map_err(|_| "grammar-utf8: manifest is not UTF-8".to_string())?;
    if !text.ends_with('\n') {
        return Err("grammar-nonterminated: manifest must end with one LF".into());
    }
    let mut lines: Vec<&str> = text.split('\n').collect();
    if lines.pop() != Some("") {
        return Err("grammar-nonterminated: manifest must end with one LF".into());
    }
    if lines.iter().any(|line| line.is_empty()) {
        return Err("grammar-blank: blank lines are not allowed".into());
    }
    if lines.len() != ENTRY_COUNT {
        return Err(format!("grammar-line-count: {} lines", lines.len()));
    }
    let mut paths = Vec::with_capacity(ENTRY_COUNT);
    for line in lines {
        if starts_or_ends_with_whitespace(line) {
            return Err("grammar-whitespace: leading or trailing whitespace is not allowed".into());
        }
        if line.starts_with('#') {
            return Err("grammar-comment: comment lines are not allowed".into());
        }
        if !Path::new(line).is_absolute() {
            return Err(format!("grammar-relative: {line}"));
        }
        paths.push(line.to_string());
    }
    Ok(paths)
}

fn starts_or_ends_with_whitespace(line: &str) -> bool {
    line.starts_with(|c: char| c.is_whitespace()) || line.ends_with(|c: char| c.is_whitespace())
}

fn admit_entry(raw: &str) -> Result<PathBuf, String> {
    let canonical = match fs::canonicalize(raw) {
        Ok(path) => path,
        Err(err) if err.kind() == ErrorKind::NotFound => {
            return Err(format!("entry-missing: {raw}"));
        }
        Err(err) if err.kind() == ErrorKind::PermissionDenied => {
            return Err(format!("entry-unreadable: {raw}: {err}"));
        }
        Err(err) => return Err(format!("entry-missing: {raw}: {err}")),
    };
    let meta = match fs::metadata(&canonical) {
        Ok(meta) => meta,
        Err(err) if err.kind() == ErrorKind::PermissionDenied => {
            return Err(format!("entry-unreadable: {}: {err}", canonical.display()));
        }
        Err(err) => return Err(format!("entry-missing: {}: {err}", canonical.display())),
    };
    if !meta.file_type().is_file() {
        return Err(format!("entry-nonregular: {}", canonical.display()));
    }
    let text = canonical.to_str().ok_or_else(|| {
        format!("entry-nonregular: canonical path is not Unicode: {}", canonical.display())
    })?;
    if text.contains(['\n', '\r', '\0']) {
        return Err(format!("entry-nonregular: canonical path contains a line control: {text}"));
    }
    File::open(&canonical).map_err(|err| format!("entry-unreadable: {text}: {err}"))?;
    Ok(canonical)
}

fn reject_duplicate_paths(paths: &[PathBuf]) -> Result<(), String> {
    for index in 1..paths.len() {
        if paths[..index].contains(&paths[index]) {
            return Err(format!("entry-duplicate: {}", paths[index].display()));
        }
    }
    Ok(())
}

fn require_anchor_once(paths: &[PathBuf], data_anchor: &Path) -> Result<(), String> {
    let anchor = match fs::canonicalize(data_anchor) {
        Ok(path) => path,
        Err(err) => {
            return Err(format!(
                "entry-missing-anchor: unresolved {}: {err}",
                data_anchor.display()
            ));
        }
    };
    let count = paths.iter().filter(|path| *path == &anchor).count();
    if count != 1 {
        return Err(format!(
            "entry-missing-anchor: absent-from-list {}: count {count}",
            anchor.display()
        ));
    }
    Ok(())
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use std::io::Write;
    use std::os::unix::fs::{symlink, PermissionsExt};
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::{SystemTime, UNIX_EPOCH};

    static CASE_SEQ: AtomicU64 = AtomicU64::new(0);

    struct ResetMode<'a> {
        path: &'a Path,
        mode: u32,
    }

    impl Drop for ResetMode<'_> {
        fn drop(&mut self) {
            let perms = fs::Permissions::from_mode(self.mode);
            let _ = fs::set_permissions(self.path, perms);
        }
    }

    fn set_mode(path: &Path, bits: u32) {
        let mut perms = fs::metadata(path).unwrap().permissions();
        perms.set_mode(bits);
        fs::set_permissions(path, perms).unwrap();
    }

    fn fixture_root() -> PathBuf {
        let raw = std::env::var("RO_ORDERED_TEST_ROOT")
            .expect("RO_ORDERED_TEST_ROOT must name the exclusive fixture directory");
        let path = PathBuf::from(raw);
        assert!(path.is_absolute(), "RO_ORDERED_TEST_ROOT must be absolute");
        assert!(path.is_dir(), "RO_ORDERED_TEST_ROOT must already exist");
        path
    }

    fn fresh(name: &str) -> PathBuf {
        let tick = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let seq = CASE_SEQ.fetch_add(1, Ordering::Relaxed);
        let dir = fixture_root().join(format!("{name}-{seq}-{tick}"));
        fs::create_dir(&dir).unwrap();
        set_mode(&dir, 0o700);
        dir
    }

    fn ensure_dir(path: &Path) {
        fs::create_dir(path).unwrap();
        set_mode(path, 0o700);
    }

    fn write_file(path: &Path, bytes: &[u8]) {
        fs::write(path, bytes).unwrap();
        set_mode(path, 0o600);
    }

    fn open_fd_count() -> usize {
        fs::read_dir("/dev/fd").unwrap().count()
    }

    struct LaidOut {
        state: PathBuf,
        manifest: PathBuf,
        files: Vec<PathBuf>,
        anchor: PathBuf,
        body: Vec<u8>,
    }

    fn lay_out(case: &Path) -> LaidOut {
        let state = case.join("state");
        ensure_dir(&state);
        let archives = case.join("archives");
        ensure_dir(&archives);
        let names = ["one.grf", "two.grf", "my archive.grf", "anchor.grf", "five.grf"];
        let mut files = Vec::new();
        for (index, name) in names.iter().enumerate() {
            let path = archives.join(name);
            write_file(&path, format!("payload-{index}\n").as_bytes());
            files.push(fs::canonicalize(&path).unwrap());
        }
        let anchor = files[3].clone();
        let mut text = String::new();
        for path in &files {
            text.push_str(path.to_str().unwrap());
            text.push('\n');
        }
        let body = text.into_bytes();
        let manifest = state.join(MANIFEST_NAME);
        write_file(&manifest, &body);
        LaidOut {
            state,
            manifest,
            files,
            anchor,
            body,
        }
    }

    fn expect_err(state: &Path, anchor: &Path, body: &[u8], prefix: &str) {
        let manifest = state.join(MANIFEST_NAME);
        write_file(&manifest, body);
        let err = read_ordered_archives(state, anchor, false).unwrap_err();
        assert!(
            err.starts_with(prefix),
            "error `{err}` does not start with `{prefix}`"
        );
        assert_eq!(fs::read(&manifest).unwrap(), body, "manifest bytes changed");
    }

    #[test]
    fn missing_list_keeps_legacy_slots_without_creating_state() {
        let case = fresh("legacy-absent");
        let state = case.join("state");
        let missing_anchor = case.join("no-such-anchor");
        assert_eq!(read_ordered_archives(&state, &missing_anchor, false).unwrap(), None);
        assert_eq!(read_ordered_archives(&state, &missing_anchor, true).unwrap(), None);
        assert!(!state.exists());

        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        assert_eq!(read_ordered_archives(&state, &anchor, false).unwrap(), None);
        assert_eq!(read_ordered_archives(&state, &anchor, true).unwrap(), None);
        assert!(!state.join(MANIFEST_NAME).exists());
        assert_eq!(fs::read_dir(&state).unwrap().count(), 0);
    }

    #[test]
    fn state_file_is_not_treated_as_a_missing_list() {
        let case = fresh("state-file");
        let state = case.join("not-a-directory");
        write_file(&state, b"state");
        let err = read_ordered_archives(&state, &case.join("anchor"), false).unwrap_err();
        assert!(err.starts_with("manifest-io"), "{err}");
        assert_eq!(fs::read(&state).unwrap(), b"state");
    }

    #[test]
    fn ordered_five_preserves_spaces_order_canonical_anchor_and_bytes() {
        let case = fresh("ordered-five");
        let state = case.join("state");
        ensure_dir(&state);
        let archives = case.join("archives");
        ensure_dir(&archives);
        let specs = [
            ("z archive.grf", "body-z"),
            ("y 客戶端.grf", "body-y"),
            ("x third.grf", "body-x"),
            ("anchor.grf", "body-anchor"),
            ("m last.grf", "body-m"),
        ];
        let mut files = Vec::new();
        for (name, body) in specs {
            let path = archives.join(name);
            write_file(&path, body.as_bytes());
            files.push(fs::canonicalize(&path).unwrap());
        }
        let via_link = archives.join("via-link.grf");
        symlink(&files[2], &via_link).unwrap();
        let anchor_link = case.join("anchor-link");
        symlink(&files[3], &anchor_link).unwrap();
        let case_text = case.to_str().unwrap();
        let lexical = format!("{case_text}/archives/../archives/z archive.grf");
        let listed = [
            lexical,
            files[1].to_str().unwrap().to_string(),
            via_link.to_str().unwrap().to_string(),
            files[3].to_str().unwrap().to_string(),
            files[4].to_str().unwrap().to_string(),
        ];
        let mut body = String::new();
        for line in &listed {
            assert!(!line.ends_with(|c: char| c.is_whitespace()));
            body.push_str(line);
            body.push('\n');
        }
        let manifest = state.join(MANIFEST_NAME);
        write_file(&manifest, body.as_bytes());
        let expected = vec![
            fs::canonicalize(Path::new(&listed[0])).unwrap(),
            files[1].clone(),
            files[2].clone(),
            files[3].clone(),
            files[4].clone(),
        ];
        let mut sorted = expected.clone();
        sorted.sort();
        assert_ne!(expected, sorted, "fixture order must differ from sorted order");
        assert!(expected.iter().all(|path| {
            path.components().all(|component| component != std::path::Component::ParentDir)
        }));
        assert_eq!(expected.iter().filter(|path| *path == &files[3]).count(), 1);

        let before_fds = open_fd_count();
        let got = read_ordered_archives(&state, &anchor_link, false).unwrap();
        assert_eq!(got, Some(expected));
        assert_eq!(open_fd_count(), before_fds, "opened descriptors were left open");
        assert_eq!(fs::read(&manifest).unwrap(), body.as_bytes());
        for (path, (_, payload)) in files.iter().zip(specs) {
            assert_eq!(fs::read(path).unwrap(), payload.as_bytes());
        }
        let names: Vec<_> = fs::read_dir(&state).unwrap().map(|entry| entry.unwrap().file_name()).collect();
        assert_eq!(names, vec![std::ffi::OsString::from(MANIFEST_NAME)]);
    }

    #[test]
    fn present_list_refuses_optional_archive_slots() {
        let case = fresh("conflict");
        let laid = lay_out(&case);
        let err = read_ordered_archives(&laid.state, &laid.anchor, true).unwrap_err();
        assert!(err.starts_with("optional-slot-conflict"), "{err}");
        assert_eq!(fs::read(&laid.manifest).unwrap(), laid.body);

        write_file(&laid.manifest, b"not-a-valid-list");
        let err = read_ordered_archives(&laid.state, &laid.anchor, true).unwrap_err();
        assert!(err.starts_with("optional-slot-conflict"), "{err}");
        assert_eq!(fs::read(&laid.manifest).unwrap(), b"not-a-valid-list");
        assert!(read_ordered_archives(&laid.state, &laid.anchor, true).unwrap_err().starts_with("optional-slot-conflict"));
    }

    #[test]
    fn four_lines_are_refused() {
        let case = fresh("four");
        let state = case.join("state");
        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        let body = sample_lines(&case, 4);
        expect_err(&state, &anchor, &body, "grammar-line-count:");
    }

    #[test]
    fn six_lines_are_refused() {
        let case = fresh("six");
        let state = case.join("state");
        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        let body = sample_lines(&case, 6);
        expect_err(&state, &anchor, &body, "grammar-line-count:");
    }

    #[test]
    fn blank_line_is_refused() {
        let case = fresh("blank");
        let state = case.join("state");
        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        let mut body = sample_lines(&case, 4);
        body.extend_from_slice(b"\n");
        body.extend_from_slice(format!("{}/archives/extra.grf\n", case.display()).as_bytes());
        expect_err(&state, &anchor, &body, "grammar-blank:");
    }

    #[test]
    fn missing_terminal_lf_is_refused() {
        let case = fresh("unterminated");
        let state = case.join("state");
        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        let mut body = sample_lines(&case, 5);
        body.pop();
        expect_err(&state, &anchor, &body, "grammar-nonterminated:");
    }

    #[test]
    fn empty_manifest_is_present_and_refused() {
        let case = fresh("empty");
        let state = case.join("state");
        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        expect_err(&state, &anchor, b"", "grammar-nonterminated:");
    }

    #[test]
    fn carriage_return_is_refused() {
        let case = fresh("cr");
        let state = case.join("state");
        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        let mut body = sample_lines(&case, 5);
        body.splice(1..1, b"\r".iter().copied());
        expect_err(&state, &anchor, &body, "grammar-cr:");
    }

    #[test]
    fn nul_is_refused() {
        let case = fresh("nul");
        let state = case.join("state");
        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        let mut body = sample_lines(&case, 5);
        body.insert(3, 0);
        expect_err(&state, &anchor, &body, "grammar-nul:");
    }

    #[test]
    fn invalid_utf8_is_refused() {
        let case = fresh("utf8");
        let state = case.join("state");
        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        let mut body = sample_lines(&case, 5);
        body.insert(2, 0xff);
        expect_err(&state, &anchor, &body, "grammar-utf8:");
    }

    #[test]
    fn over_cap_is_refused_and_exact_cap_is_grammar() {
        let case = fresh("cap");
        let state = case.join("state");
        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        let over = vec![b'x'; (MANIFEST_CAP as usize) + 1];
        expect_err(&state, &anchor, &over, "manifest-over-cap:");
        let exact = vec![b'y'; MANIFEST_CAP as usize];
        let manifest = state.join(MANIFEST_NAME);
        write_file(&manifest, &exact);
        let err = read_ordered_archives(&state, &anchor, false).unwrap_err();
        assert!(err.starts_with("grammar-"), "exact cap must pass the size gate, got `{err}`");
        assert!(!err.starts_with("manifest-over-cap:"), "{err}");
        assert_eq!(fs::read(&manifest).unwrap(), exact);
    }

    #[test]
    fn relative_path_is_refused_without_trimming() {
        let case = fresh("relative");
        let state = case.join("state");
        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        let mut lines = Vec::new();
        lines.push("archives/relative.grf".to_string());
        for index in 1..ENTRY_COUNT {
            lines.push(format!("{}/archives/file-{index}.grf", case.display()));
        }
        let body = lines.join("\n") + "\n";
        expect_err(&state, &anchor, body.as_bytes(), "grammar-relative:");
    }

    #[test]
    fn leading_or_trailing_whitespace_is_refused() {
        let case = fresh("whitespace");
        let state = case.join("state");
        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        let real = case.join("archives");
        ensure_dir(&real);
        write_file(&real.join("file.grf"), b"file");
        let canonical = fs::canonicalize(real.join("file.grf")).unwrap();
        let text = canonical.to_str().unwrap();
        let trailing = format!("{text} \n{text}\n{text}\n{text}\n{text}\n");
        expect_err(&state, &anchor, trailing.as_bytes(), "grammar-whitespace:");
        let leading = format!(" {text}\n{text}\n{text}\n{text}\n{text}\n");
        expect_err(&state, &anchor, leading.as_bytes(), "grammar-whitespace:");
    }

    #[test]
    fn comment_line_is_refused() {
        let case = fresh("comment");
        let state = case.join("state");
        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        let mut body = sample_lines(&case, 4);
        body.extend_from_slice(b"# not an archive\n");
        expect_err(&state, &anchor, &body, "grammar-comment:");
    }

    #[test]
    fn duplicate_lexical_and_symlink_aliases_are_refused() {
        let case = fresh("duplicate");
        let laid = lay_out(&case);
        let case_text = case.to_str().unwrap();
        let lexical = format!("{case_text}/archives/../archives/one.grf");
        let mut lines = vec![lexical, laid.files[0].to_str().unwrap().to_string()];
        lines.extend(laid.files[2..].iter().map(|path| path.to_str().unwrap().to_string()));
        assert_eq!(lines.len(), ENTRY_COUNT);
        let body = lines.join("\n") + "\n";
        expect_err(&laid.state, &laid.anchor, body.as_bytes(), "entry-duplicate:");

        let alias = case.join("archives").join("one-alias.grf");
        symlink(&laid.files[0], &alias).unwrap();
        let mut linked = vec![
            laid.files[0].to_str().unwrap().to_string(),
            alias.to_str().unwrap().to_string(),
        ];
        linked.extend(laid.files[2..].iter().map(|path| path.to_str().unwrap().to_string()));
        let body = linked.join("\n") + "\n";
        expect_err(&laid.state, &laid.anchor, body.as_bytes(), "entry-duplicate:");
    }

    #[test]
    fn repeated_anchor_line_is_a_duplicate() {
        let case = fresh("anchor-twice");
        let laid = lay_out(&case);
        let anchor = laid.anchor.to_str().unwrap();
        let lines = [
            anchor,
            anchor,
            laid.files[0].to_str().unwrap(),
            laid.files[1].to_str().unwrap(),
            laid.files[2].to_str().unwrap(),
        ];
        let body = lines.join("\n") + "\n";
        expect_err(&laid.state, &laid.anchor, body.as_bytes(), "entry-duplicate:");
    }

    #[test]
    fn missing_anchor_is_refused() {
        let case = fresh("missing-anchor");
        let laid = lay_out(&case);
        let other = case.join("other-anchor.grf");
        write_file(&other, b"other");
        let err = read_ordered_archives(&laid.state, &other, false).unwrap_err();
        assert!(err.starts_with("entry-missing-anchor:"), "{err}");
        assert!(err.contains("absent-from-list"), "{err}");
        assert_eq!(fs::read(&laid.manifest).unwrap(), laid.body);
    }

    #[test]
    fn unresolved_anchor_is_refused() {
        let case = fresh("unresolved-anchor");
        let laid = lay_out(&case);
        let missing = case.join("missing-anchor.grf");
        let err = read_ordered_archives(&laid.state, &missing, false).unwrap_err();
        assert!(err.starts_with("entry-missing-anchor:"), "{err}");
        assert!(err.contains("unresolved"), "{err}");
        assert_eq!(fs::read(&laid.manifest).unwrap(), laid.body);
    }

    #[test]
    fn missing_entry_is_refused() {
        let case = fresh("missing-entry");
        let state = case.join("state");
        ensure_dir(&state);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        let mut lines = vec![anchor.to_str().unwrap().to_string()];
        for index in 1..ENTRY_COUNT {
            let path = case.join(format!("present-{index}.grf"));
            write_file(&path, b"present");
            lines.push(fs::canonicalize(path).unwrap().to_str().unwrap().to_string());
        }
        lines[4] = format!("{}/absent-entry.grf", case.display());
        let body = lines.join("\n") + "\n";
        expect_err(&state, &anchor, body.as_bytes(), "entry-missing:");
    }

    #[test]
    fn unreadable_entry_is_refused_and_mode_is_restored() {
        let case = fresh("unreadable-entry");
        let laid = lay_out(&case);
        let blocked = &laid.files[0];
        let _restore = ResetMode {
            path: blocked,
            mode: 0o600,
        };
        set_mode(blocked, 0o000);
        let err = read_ordered_archives(&laid.state, &laid.anchor, false).unwrap_err();
        assert!(err.starts_with("entry-unreadable:"), "{err}");
        assert_eq!(fs::read(&laid.manifest).unwrap(), laid.body);
    }

    #[test]
    fn nonregular_entry_is_refused() {
        let case = fresh("nonregular-entry");
        let laid = lay_out(&case);
        let directory = case.join("archives").join("a-directory");
        ensure_dir(&directory);
        let mut lines: Vec<String> = laid.files.iter().map(|path| path.to_str().unwrap().to_string()).collect();
        lines[1] = fs::canonicalize(&directory).unwrap().to_str().unwrap().to_string();
        let body = lines.join("\n") + "\n";
        expect_err(&laid.state, &laid.anchor, body.as_bytes(), "entry-nonregular:");
    }

    #[test]
    fn manifest_symlink_is_refused() {
        let case = fresh("manifest-symlink");
        let laid = lay_out(&case);
        let real = case.join("real-list");
        fs::rename(&laid.manifest, &real).unwrap();
        set_mode(&real, 0o600);
        symlink(&real, &laid.manifest).unwrap();
        let err = read_ordered_archives(&laid.state, &laid.anchor, false).unwrap_err();
        assert!(err.starts_with("manifest-symlink:"), "{err}");
        assert_eq!(fs::read(&real).unwrap(), laid.body);
    }

    #[test]
    fn manifest_hardlink_is_refused() {
        let case = fresh("manifest-hardlink");
        let laid = lay_out(&case);
        let alias = laid.state.join("list-alias");
        fs::hard_link(&laid.manifest, &alias).unwrap();
        set_mode(&alias, 0o600);
        let err = read_ordered_archives(&laid.state, &laid.anchor, false).unwrap_err();
        assert!(err.starts_with("manifest-hardlink:"), "{err}");
        assert_eq!(fs::read(&laid.manifest).unwrap(), laid.body);
    }

    #[test]
    fn manifest_directory_is_refused() {
        let case = fresh("manifest-dir");
        let state = case.join("state");
        ensure_dir(&state);
        let manifest = state.join(MANIFEST_NAME);
        ensure_dir(&manifest);
        let anchor = case.join("anchor.grf");
        write_file(&anchor, b"anchor");
        let err = read_ordered_archives(&state, &anchor, false).unwrap_err();
        assert!(err.starts_with("manifest-nonregular:"), "{err}");
        assert!(manifest.is_dir());
    }

    #[test]
    fn unreadable_manifest_is_refused_and_mode_is_restored() {
        let case = fresh("unreadable-manifest");
        let laid = lay_out(&case);
        let _restore = ResetMode {
            path: &laid.manifest,
            mode: 0o600,
        };
        set_mode(&laid.manifest, 0o000);
        let err = read_ordered_archives(&laid.state, &laid.anchor, false).unwrap_err();
        assert!(err.starts_with("manifest-unreadable:"), "{err}");
    }

    #[test]
    fn read_time_append_replacement_and_same_length_edit_are_refused() {
        let case = fresh("mutate-append");
        let laid = lay_out(&case);
        let _guard = install_after_open_hook(append_one_byte);
        let err = read_ordered_archives(&laid.state, &laid.anchor, false).unwrap_err();
        assert!(err.starts_with("manifest-identity-changed:"), "{err}");
        assert_eq!(fs::metadata(&laid.manifest).unwrap().permissions().mode() & 0o777, 0o600);

        let case = fresh("mutate-replace");
        let laid = lay_out(&case);
        let _guard = install_after_open_hook(replace_inode);
        let err = read_ordered_archives(&laid.state, &laid.anchor, false).unwrap_err();
        assert!(err.starts_with("manifest-identity-changed:"), "{err}");
        assert_eq!(fs::metadata(&laid.manifest).unwrap().permissions().mode() & 0o777, 0o600);
        assert_eq!(fs::read(&laid.manifest).unwrap(), laid.body);

        let case = fresh("mutate-same-len");
        let laid = lay_out(&case);
        let _guard = install_after_open_hook(rewrite_same_length);
        let err = read_ordered_archives(&laid.state, &laid.anchor, false).unwrap_err();
        assert!(err.starts_with("manifest-identity-changed:"), "{err}");
        assert_eq!(fs::metadata(&laid.manifest).unwrap().len(), laid.body.len() as u64);
        assert_ne!(fs::read(&laid.manifest).unwrap(), laid.body);
        set_mode(&laid.manifest, 0o600);
    }

    fn append_one_byte(path: &Path) {
        let mut file = fs::OpenOptions::new().append(true).open(path).unwrap();
        file.write_all(b"X").unwrap();
    }

    fn replace_inode(path: &Path) {
        let bytes = fs::read(path).unwrap();
        fs::remove_file(path).unwrap();
        fs::write(path, bytes).unwrap();
        set_mode(path, 0o600);
    }

    fn rewrite_same_length(path: &Path) {
        let bytes = fs::read(path).unwrap();
        let mut flipped = bytes;
        let last = flipped.len() - 1;
        flipped[last] ^= 0x01;
        let mut file = fs::OpenOptions::new().write(true).truncate(true).open(path).unwrap();
        file.write_all(&flipped).unwrap();
    }

    fn sample_lines(case: &Path, count: usize) -> Vec<u8> {
        let mut body = String::new();
        for index in 0..count {
            body.push_str(&format!("{}/archives/file-{index}.grf\n", case.display()));
        }
        body.into_bytes()
    }
}
