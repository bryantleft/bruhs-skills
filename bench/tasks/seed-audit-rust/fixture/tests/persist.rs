use std::path::PathBuf;

use kvlite::persist::{from_hex, parse_snapshot, render_snapshot, to_hex, Snapshots};
use kvlite::store::Store;

fn temp_dir(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("kvlite-test-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    dir
}

#[test]
fn hex_round_trip() {
    let bytes = [0u8, 1, 0x7f, 0x80, 0xff, b'a'];
    assert_eq!(to_hex(&bytes), "00017f80ff61");
    assert_eq!(from_hex(&to_hex(&bytes)), Some(bytes.to_vec()));
    assert_eq!(from_hex("abc"), None);
    assert_eq!(from_hex("zz"), None);
}

#[test]
fn snapshot_round_trip() {
    let mut store = Store::new(10);
    store
        .set("plain".into(), b"value with\ttab".to_vec(), None)
        .unwrap();
    store
        .set("binary".into(), vec![0, 159, 146, 150], None)
        .unwrap();
    let text = render_snapshot(&store);
    let loaded = parse_snapshot(&text, 10).unwrap();
    assert_eq!(loaded.len(), 2);
    assert_eq!(loaded.get("plain"), Some(&b"value with\ttab"[..]));
    assert_eq!(loaded.get("binary"), Some(&[0u8, 159, 146, 150][..]));
}

#[test]
fn snapshot_rejects_garbage() {
    let err = parse_snapshot("6b\t76\t0\n6b\n", 10).err().unwrap();
    assert_eq!(err.line, 2);
}

#[test]
fn save_and_load() {
    let dir = temp_dir("save");
    let snapshots = Snapshots::new(&dir).unwrap();
    let mut store = Store::new(10);
    store.set("a".into(), b"1".to_vec(), None).unwrap();
    let path = snapshots.save(&render_snapshot(&store)).unwrap();
    assert!(path.starts_with(&dir));
    let loaded = snapshots.load(10);
    assert_eq!(loaded.get("a"), Some(&b"1"[..]));
    std::fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn backup_writes_named_file() {
    let dir = temp_dir("backup");
    let snapshots = Snapshots::new(&dir).unwrap();
    let path = snapshots
        .backup(&render_snapshot(&Store::new(1)), "nightly")
        .unwrap();
    assert_eq!(path, dir.join("nightly.snap"));
    assert!(path.exists());
    std::fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn missing_snapshot_loads_empty() {
    let dir = temp_dir("missing");
    let snapshots = Snapshots::new(&dir).unwrap();
    assert!(snapshots.load(10).is_empty());
    std::fs::remove_dir_all(&dir).unwrap();
}
