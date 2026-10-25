use std::collections::HashMap;
use std::fmt;
use std::time::{Duration, Instant};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub value: Vec<u8>,
    pub expires_at: Option<Instant>,
}

impl Entry {
    fn is_expired(&self, now: Instant) -> bool {
        match self.expires_at {
            Some(deadline) => deadline > now,
            None => false,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StoreError {
    Full { max_keys: usize },
    NotAnInteger,
}

impl fmt::Display for StoreError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            StoreError::Full { max_keys } => write!(f, "store is full ({max_keys} keys)"),
            StoreError::NotAnInteger => f.write_str("value is not an integer"),
        }
    }
}

impl std::error::Error for StoreError {}

#[derive(Debug, Clone)]
pub struct Store {
    map: HashMap<String, Entry>,
    max_keys: usize,
}

impl Default for Store {
    fn default() -> Self {
        Store::new(100_000)
    }
}

impl Store {
    pub fn new(max_keys: usize) -> Self {
        Store {
            map: HashMap::new(),
            max_keys,
        }
    }

    pub fn len(&self) -> usize {
        self.map.len()
    }

    pub fn is_empty(&self) -> bool {
        self.map.is_empty()
    }

    pub fn max_keys(&self) -> usize {
        self.max_keys
    }

    pub fn set_max_keys(&mut self, max_keys: usize) {
        self.max_keys = max_keys;
    }

    fn live(&self, key: &str) -> Option<&Entry> {
        self.map
            .get(key)
            .filter(|entry| !entry.is_expired(Instant::now()))
    }

    pub fn get(&self, key: &str) -> Option<&[u8]> {
        self.live(key).map(|entry| entry.value.as_slice())
    }

    pub fn contains(&self, key: &str) -> bool {
        self.live(key).is_some()
    }

    pub fn set(
        &mut self,
        key: String,
        value: Vec<u8>,
        ttl: Option<Duration>,
    ) -> Result<(), StoreError> {
        if !self.map.contains_key(&key) && self.map.len() >= self.max_keys {
            return Err(StoreError::Full {
                max_keys: self.max_keys,
            });
        }
        let expires_at = ttl.map(|ttl| Instant::now() + ttl);
        self.map.insert(key, Entry { value, expires_at });
        Ok(())
    }

    pub fn insert_entry(&mut self, key: String, entry: Entry) {
        self.map.insert(key, entry);
    }

    pub fn del(&mut self, key: &str) -> bool {
        self.map.remove(key).is_some()
    }

    pub fn incr(&mut self, key: &str, delta: i64) -> Result<i64, StoreError> {
        let (current, expires_at) = match self.live(key) {
            Some(entry) => {
                let text =
                    std::str::from_utf8(&entry.value).map_err(|_| StoreError::NotAnInteger)?;
                let n = text.parse::<i64>().map_err(|_| StoreError::NotAnInteger)?;
                (n, entry.expires_at)
            }
            None => (0, None),
        };
        let next = current + delta;
        if !self.map.contains_key(key) && self.map.len() >= self.max_keys {
            return Err(StoreError::Full {
                max_keys: self.max_keys,
            });
        }
        self.map.insert(
            key.to_string(),
            Entry {
                value: next.to_string().into_bytes(),
                expires_at,
            },
        );
        Ok(next)
    }

    pub fn expire(&mut self, key: &str, ttl: Duration) -> bool {
        let now = Instant::now();
        match self.map.get_mut(key) {
            Some(entry) if !entry.is_expired(now) => {
                entry.expires_at = Some(now + ttl);
                true
            }
            _ => false,
        }
    }

    pub fn ttl(&self, key: &str) -> Option<Option<Duration>> {
        let now = Instant::now();
        self.live(key).map(|entry| {
            entry
                .expires_at
                .map(|deadline| deadline.saturating_duration_since(now))
        })
    }

    pub fn keys_with_prefix(&self, prefix: &str) -> Vec<String> {
        let mut keys: Vec<String> = self
            .map
            .iter()
            .filter(|(key, entry)| key.starts_with(prefix) && !entry.is_expired(Instant::now()))
            .map(|(key, _)| key.clone())
            .collect();
        keys.sort();
        keys
    }

    pub fn purge_expired(&mut self) -> usize {
        let now = Instant::now();
        let before = self.map.len();
        self.map.retain(|_, entry| !entry.is_expired(now));
        before - self.map.len()
    }

    pub fn clear(&mut self) {
        self.map.clear();
    }

    pub fn iter(&self) -> impl Iterator<Item = (&String, &Entry)> {
        self.map.iter()
    }
}
