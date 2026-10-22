//! Root-owned synthetic integration checks. Run ONLY this module's filter.
//! Requires an absolute, canonical, precreated0700 RO_STACK_INTEGRATION_TEST_ROOT.
//! Every test owns a fresh exclusive child; no cleanup or app entry point is used.

use super::link;
use crate::config::Config;
use std::collections::BTreeMap;
use std::fs::{self, DirBuilder, OpenOptions};
use std::io::Write;
use std::os::unix::fs::{DirBuilderExt, MetadataExt, OpenOptionsExt};
use std::path::{Path, PathBuf};

#[derive(Debug, PartialEq, Eq)]
struct Entry {
    dev: u64,
    ino: u64,
    mode: u32,
    nlink: u64,
    len: u64,
    mtime: (i64, i64),
    ctime: (i64, i64),
    bytes: Vec<u8>,
}

fn snapshot(path: &Path) -> BTreeMap<PathBuf, Entry> {
    fn walk(base: &Path, path: &Path, out: &mut BTreeMap<PathBuf, Entry>) {
        let meta = fs::symlink_metadata(path).unwrap();
        assert!(!meta.file_type().is_symlink(), "fixture link: {}", path.display());
        assert!(meta.is_file() || meta.is_dir(), "fixture special file");
        let bytes = if meta.is_file() { fs::read(path).unwrap() } else { Vec::new() };
        out.insert(path.strip_prefix(base).unwrap().to_path_buf(), Entry {
            dev: meta.dev(), ino: meta.ino(), mode: meta.mode(), nlink: meta.nlink(),
            len: meta.len(), mtime: (meta.mtime(), meta.mtime_nsec()),
            ctime: (meta.ctime(), meta.ctime_nsec()), bytes,
        });
        if meta.is_dir() {
            for entry in fs::read_dir(path).unwrap() {
                walk(base, &entry.unwrap().path(), out);
            }
        }
    }
    let mut out = BTreeMap::new();
    walk(path, path, &mut out);
    out
}

fn private_dir(path: &Path) {
    match fs::symlink_metadata(path) {
        Ok(meta) => {
            assert!(meta.is_dir() && !meta.file_type().is_symlink());
            assert_eq!(meta.mode() & 0o777, 0o700, "private dir: {}", path.display());
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            private_dir(path.parent().unwrap());
            DirBuilder::new().mode(0o700).create(path).unwrap();
        }
        Err(error) => panic!("fixture metadata: {error}"),
    }
}

fn write_new(path: &Path, bytes: &[u8]) {
    private_dir(path.parent().unwrap());
    let mut file = OpenOptions::new().write(true).create_new(true).mode(0o600).open(path).unwrap();
    file.write_all(bytes).unwrap();
    file.sync_all().unwrap();
}

struct Fixture {
    case: PathBuf,
    cfg: Config,
    archives: Vec<PathBuf>,
}

impl Fixture {
    fn new(name: &str) -> Self {
        let root = PathBuf::from(std::env::var_os("RO_STACK_INTEGRATION_TEST_ROOT")
            .expect("root must admit a fresh private fixture root"));
        assert!(root.is_absolute());
        let meta = fs::symlink_metadata(&root).unwrap();
        assert!(meta.is_dir() && !meta.file_type().is_symlink());
        assert_eq!(meta.mode() & 0o777, 0o700);
        assert_eq!(fs::canonicalize(&root).unwrap(), root, "fixture root must be canonical");
        let case = root.join(name);
        DirBuilder::new().mode(0o700).create(&case).expect("exclusive case already exists; preserve it");
        let cfg = Config {
            root: case.join("app"), state: case.join("state"),
            nebula_home: case.join("unused-nebula-home"), nebula: case.join("unused-nebula"),
            docker: case.join("unused-docker"), image: String::new(), db_image: String::new(),
            app_version: None, ports: crate::ports::Ports::DEFAULT,
        };
        write_new(&cfg.root.join("config/Config.local.js"),
            b"window.ROConfigLocal = {\nrenewal: true,\npacketver: 20221005,\nlangtype: 0,\n};\n");
        write_new(&cfg.root.join("config/index.html"), b"synthetic entry; never served\n");
        write_new(&cfg.state.join("settings.json"), b"{\"game_text\":\"client_taiwan\"}\n");
        private_dir(&case.join("evidence"));
        let mut archives = Vec::new();
        for i in 0..5 {
            let client = case.join("clients").join(format!("client {i}"));
            let archive = client.join(format!("archive {i}"));
            write_new(&archive, format!("authored fake archive {i}; never parsed\n").as_bytes());
            write_new(&client.join("System/origin.txt"), format!("client {i}\n").as_bytes());
            write_new(&client.join("System/itemInfo.lua"), format!("native item table {i}\n").as_bytes());
            write_new(&client.join("BGM/theme.mp3"), format!("fake music {i}\n").as_bytes());
            write_new(&client.join("AI/AI.lua"), format!("fake AI {i}\n").as_bytes());
            archives.push(fs::canonicalize(archive).unwrap());
        }
        Self { case, cfg, archives }
    }

    fn list_bytes(&self, order: &[usize]) -> Vec<u8> {
        order.iter().map(|i| format!("{}\n", self.archives[*i].display())).collect::<String>().into_bytes()
    }

    fn expected_ini(&self, order: &[usize]) -> Vec<u8> {
        let mut value = String::from("[Data]\n");
        for (index, archive) in order.iter().enumerate() {
            value.push_str(&format!("{index}={}\n", self.archives[*archive].display()));
        }
        value.into_bytes()
    }

    fn source_snapshot(&self) -> (BTreeMap<PathBuf, Entry>, BTreeMap<PathBuf, Entry>) {
        (snapshot(&self.cfg.root), snapshot(&self.case.join("clients")))
    }

    fn assert_anchor(&self) {
        for (name, directory) in [("bgm.path", "BGM"), ("ai.path", "AI")] {
            let expected = fs::canonicalize(self.archives[2].parent().unwrap().join(directory)).unwrap();
            assert_eq!(fs::read(self.cfg.state.join("asset-config").join(name)).unwrap(),
                expected.to_str().unwrap().as_bytes());
        }
        assert_eq!(fs::read(self.cfg.state.join("assets/System/origin.txt")).unwrap(), b"client 2\n");
        assert_eq!(fs::read(self.cfg.state.join("assets/System/itemInfo.lua")).unwrap(), b"native item table 2\n");
    }

    fn assert_private_and_bounded(&self) {
        let mut children: Vec<_> = fs::read_dir(&self.case).unwrap()
            .map(|entry| entry.unwrap().file_name().to_str().unwrap().to_owned()).collect();
        children.sort();
        assert_eq!(children, ["app", "clients", "evidence", "state"]);
        for (path, entry) in snapshot(&self.case) {
            let is_dir = entry.mode & 0o170000 == 0o040000;
            assert_eq!(entry.mode & 0o777, if is_dir { 0o700 } else { 0o600 },
                "root must run with process-local umask077: {}", path.display());
            if !is_dir { assert_eq!(entry.nlink, 1); }
        }
    }
}

#[test]
fn five_order_anchor_and_ordered_fingerprint_are_preserved() {
    let fixture = Fixture::new("five-order");
    let first_order = [4, 0, 3, 1, 2]; // Anchor is deliberately last, not first.
    let manifest = fixture.cfg.state.join("asset-archives.list");
    write_new(&manifest, &fixture.list_bytes(&first_order));
    let before = fixture.source_snapshot();
    let list_before = snapshot(&manifest);
    let args = vec![fixture.archives[2].to_str().unwrap().to_owned()];
    link(&fixture.cfg, &args).unwrap();
    assert_eq!(fs::read(fixture.cfg.state.join("asset-config/DATA.INI")).unwrap(), fixture.expected_ini(&first_order));
    fixture.assert_anchor();
    assert_eq!(fixture.source_snapshot(), before);
    assert_eq!(snapshot(&manifest), list_before);
    let first_id = fs::read(fixture.cfg.state.join("assets/overlay.id")).unwrap();
    assert_eq!(first_id.len(), 16);
    write_new(&fixture.case.join("evidence/first-list"), &fixture.list_bytes(&first_order));
    write_new(&fixture.case.join("evidence/first-DATA.INI"), &fixture.expected_ini(&first_order));
    write_new(&fixture.case.join("evidence/first-overlay.id"), &first_id);
    // Only this authored fixture list is changed, after first outputs are retained.
    let second_order = [0, 4, 3, 1, 2];
    fs::write(&manifest, fixture.list_bytes(&second_order)).unwrap();
    let second_list_before = snapshot(&manifest);
    link(&fixture.cfg, &args).unwrap();
    assert_eq!(fs::read(fixture.cfg.state.join("asset-config/DATA.INI")).unwrap(), fixture.expected_ini(&second_order));
    assert_ne!(fs::read(fixture.cfg.state.join("assets/overlay.id")).unwrap(), first_id);
    fixture.assert_anchor();
    assert_eq!(fixture.source_snapshot(), before);
    assert_eq!(snapshot(&manifest), second_list_before);
    fixture.assert_private_and_bounded();
}

#[test]
fn missing_list_retains_legacy_vector_and_data_anchor() {
    let fixture = Fixture::new("legacy-none");
    let before = fixture.source_snapshot();
    let args = vec![
        fixture.archives[2].to_str().unwrap().to_owned(),
        fixture.archives[0].to_str().unwrap().to_owned(),
        fixture.archives[1].to_str().unwrap().to_owned(),
        String::new(),
        fixture.archives[4].to_str().unwrap().to_owned(),
    ];
    link(&fixture.cfg, &args).unwrap();
    assert_eq!(fs::read(fixture.cfg.state.join("asset-config/DATA.INI")).unwrap(), fixture.expected_ini(&[1, 0, 2, 4]));
    fixture.assert_anchor();
    assert_eq!(fixture.source_snapshot(), before);
    assert!(!fixture.cfg.state.join("asset-archives.list").exists());
    fixture.assert_private_and_bounded();
}

#[test]
fn invalid_manifest_precedes_transaction_and_preserves_state() {
    let fixture = Fixture::new("reject-before-transaction");
    write_new(&fixture.cfg.state.join("asset-archives.list"), &fixture.list_bytes(&[0, 1, 2, 3]));
    // Transaction::begin would create its lock before reading this invalid journal.
    // Thus even a failure in recovery distinguishes accidental transaction entry.
    write_new(&fixture.cfg.state.join(".asset-update/journal"), b"invalid recovery tripwire\n");
    write_new(&fixture.cfg.state.join("assets/sentinel"), b"existing synthetic assets\n");
    write_new(&fixture.cfg.state.join("asset-config/sentinel"), b"existing synthetic config\n");
    let source_before = fixture.source_snapshot();
    let state_before = snapshot(&fixture.cfg.state);
    let args = vec![fixture.archives[2].to_str().unwrap().to_owned()];
    let result = link(&fixture.cfg, &args);
    assert!(result.as_ref().unwrap_err().starts_with("grammar-line-count:"),
        "must reach the selector count refusal, not an unrelated earlier failure: {result:?}");
    assert_eq!(snapshot(&fixture.cfg.state), state_before);
    assert_eq!(fixture.source_snapshot(), source_before);
    assert!(!fixture.cfg.state.join(".asset-link.lock").exists());
    write_new(&fixture.case.join("evidence/rejection.txt"), result.unwrap_err().as_bytes());
    fixture.assert_private_and_bounded();
}
