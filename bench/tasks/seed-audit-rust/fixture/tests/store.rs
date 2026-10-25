use kvlite::store::{Store, StoreError};

#[test]
fn set_get_del() {
    let mut store = Store::new(10);
    store.set("a".into(), b"1".to_vec(), None).unwrap();
    assert_eq!(store.get("a"), Some(&b"1"[..]));
    assert!(store.contains("a"));
    assert!(store.del("a"));
    assert!(!store.del("a"));
    assert_eq!(store.get("a"), None);
}

#[test]
fn overwrite_keeps_one_key() {
    let mut store = Store::new(10);
    store.set("a".into(), b"1".to_vec(), None).unwrap();
    store.set("a".into(), b"2".to_vec(), None).unwrap();
    assert_eq!(store.len(), 1);
    assert_eq!(store.get("a"), Some(&b"2"[..]));
}

#[test]
fn full_store_rejects_new_keys_but_allows_updates() {
    let mut store = Store::new(2);
    store.set("a".into(), b"1".to_vec(), None).unwrap();
    store.set("b".into(), b"1".to_vec(), None).unwrap();
    assert_eq!(
        store.set("c".into(), b"1".to_vec(), None),
        Err(StoreError::Full { max_keys: 2 })
    );
    store.set("a".into(), b"9".to_vec(), None).unwrap();
}

#[test]
fn incr_counts_from_zero() {
    let mut store = Store::new(10);
    assert_eq!(store.incr("hits", 1), Ok(1));
    assert_eq!(store.incr("hits", 5), Ok(6));
    assert_eq!(store.incr("hits", -2), Ok(4));
    assert_eq!(store.get("hits"), Some(&b"4"[..]));
}

#[test]
fn incr_rejects_non_integers() {
    let mut store = Store::new(10);
    store.set("name".into(), b"ada".to_vec(), None).unwrap();
    assert_eq!(store.incr("name", 1), Err(StoreError::NotAnInteger));
}

#[test]
fn keys_by_prefix_sorted() {
    let mut store = Store::new(10);
    for key in ["user:2", "user:1", "job:1"] {
        store.set(key.into(), Vec::new(), None).unwrap();
    }
    assert_eq!(store.keys_with_prefix("user:"), vec!["user:1", "user:2"]);
    assert_eq!(store.keys_with_prefix("").len(), 3);
}

#[test]
fn ttl_of_missing_and_persistent_keys() {
    let mut store = Store::new(10);
    assert_eq!(store.ttl("nope"), None);
    store.set("a".into(), b"1".to_vec(), None).unwrap();
    assert_eq!(store.ttl("a"), Some(None));
}
