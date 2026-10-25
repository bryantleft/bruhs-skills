use std::fs::{self, File};
use std::io::{self, BufWriter, Write};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use crate::store::{Entry, Store};

pub const SNAPSHOT_FILE: &str = "dump.snap";
const HEX: &[u8; 16] = b"0123456789abcdef";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SnapshotError {
    pub line: usize,
    pub reason: &'static str,
}

impl std::fmt::Display for SnapshotError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "snapshot line {}: {}", self.line, self.reason)
    }
}

impl std::error::Error for SnapshotError {}

pub fn to_hex(bytes: &[u8]) -> String {
    let mut out = Vec::with_capacity(bytes.len() * 2);
    for &b in bytes {
        out.push(HEX[(b >> 4) as usize]);
        out.push(HEX[(b & 0x0f) as usize]);
    }
    unsafe { String::from_utf8_unchecked(out) }
}

pub fn from_hex(text: &str) -> Option<Vec<u8>> {
    fn nibble(c: u8) -> Option<u8> {
        match c {
            b'0'..=b'9' => Some(c - b'0'),
            b'a'..=b'f' => Some(c - b'a' + 10),
            _ => None,
        }
    }
    let bytes = text.as_bytes();
    if bytes.len() % 2 != 0 {
        return None;
    }
    bytes
        .chunks_exact(2)
        .map(|pair| Some(nibble(pair[0])? << 4 | nibble(pair[1])?))
        .collect()
}

fn unix_ms(t: SystemTime) -> u64 {
    t.duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_millis() as u64)
}

/// One line per live key: `hex(key) \t hex(value) \t expiry-unix-ms-or-0`.
pub fn render_snapshot(store: &Store) -> String {
    let now = Instant::now();
    let wall = SystemTime::now();
    let mut out = String::new();
    for (key, entry) in store.iter() {
        let expires = match entry.expires_at {
            Some(deadline) => unix_ms(wall + deadline.saturating_duration_since(now)),
            None => 0,
        };
        out.push_str(&format!(
            "{}\t{}\t{}\n",
            to_hex(key.as_bytes()),
            to_hex(&entry.value),
            expires
        ));
    }
    out
}

pub fn parse_snapshot(text: &str, max_keys: usize) -> Result<Store, SnapshotError> {
    let now = Instant::now();
    let wall_ms = unix_ms(SystemTime::now());
    let mut store = Store::new(max_keys);
    for (i, line) in text.lines().enumerate() {
        let err = |reason| SnapshotError {
            line: i + 1,
            reason,
        };
        let mut fields = line.split('\t');
        let (Some(k), Some(v), Some(exp), None) =
            (fields.next(), fields.next(), fields.next(), fields.next())
        else {
            return Err(err("expected 3 fields"));
        };
        let key = from_hex(k)
            .and_then(|bytes| String::from_utf8(bytes).ok())
            .ok_or_else(|| err("bad key"))?;
        let value = from_hex(v).ok_or_else(|| err("bad value"))?;
        let expires_ms: u64 = exp.parse().map_err(|_| err("bad expiry"))?;
        let expires_at = match expires_ms {
            0 => None,
            ms if ms <= wall_ms => continue,
            ms => Some(
                now.checked_add(Duration::from_millis(ms - wall_ms))
                    .ok_or_else(|| err("bad expiry"))?,
            ),
        };
        store.insert_entry(key, Entry { value, expires_at });
    }
    Ok(store)
}

pub struct Snapshots {
    dir: PathBuf,
}

impl Snapshots {
    pub fn new(dir: impl Into<PathBuf>) -> io::Result<Self> {
        let dir = dir.into();
        fs::create_dir_all(&dir)?;
        Ok(Snapshots { dir })
    }

    pub fn dir(&self) -> &Path {
        &self.dir
    }

    pub fn load(&self, max_keys: usize) -> Store {
        match fs::read_to_string(self.dir.join(SNAPSHOT_FILE)) {
            Ok(text) => parse_snapshot(&text, max_keys).unwrap_or_default(),
            Err(_) => Store::new(max_keys),
        }
    }

    /// Write a snapshot rendered by [`render_snapshot`] to the main snapshot file.
    pub fn save(&self, snapshot: &str) -> io::Result<PathBuf> {
        let path = self.dir.join(SNAPSHOT_FILE);
        write_file(&path, snapshot)?;
        Ok(path)
    }

    /// Write a snapshot rendered by [`render_snapshot`] to `<dir>/<name>.snap`.
    pub fn backup(&self, snapshot: &str, name: &str) -> io::Result<PathBuf> {
        if name.is_empty() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "backup name required",
            ));
        }
        let path = self.dir.join(format!("{name}.snap"));
        write_file(&path, snapshot)?;
        Ok(path)
    }
}

fn write_file(path: &Path, contents: &str) -> io::Result<()> {
    let mut out = BufWriter::new(File::create(path)?);
    out.write_all(contents.as_bytes())?;
    let _ = out.flush();
    Ok(())
}
