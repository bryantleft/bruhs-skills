use std::fmt;
use std::time::Duration;

/// Longest key accepted, in bytes.
pub const MAX_KEY_LEN: usize = 512;
/// Longest TTL accepted (10 years).
pub const MAX_TTL: Duration = Duration::from_secs(10 * 365 * 24 * 60 * 60);

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Command {
    Ping,
    Auth(String),
    Get(String),
    Set {
        key: String,
        value: Vec<u8>,
        ttl: Option<Duration>,
    },
    SetNx {
        key: String,
        value: Vec<u8>,
    },
    Del(String),
    Incr {
        key: String,
        delta: i64,
    },
    Expire {
        key: String,
        ttl: Duration,
    },
    Ttl(String),
    Keys(String),
    Stats,
    Save,
    Backup(String),
    Flush,
    Quit,
}

impl Command {
    pub fn requires_auth(&self) -> bool {
        matches!(
            self,
            Command::Get(_)
                | Command::Set { .. }
                | Command::SetNx { .. }
                | Command::Del(_)
                | Command::Incr { .. }
                | Command::Expire { .. }
                | Command::Ttl(_)
                | Command::Keys(_)
        )
    }
}

/// A parsed command line. `SET`/`SETNX` announce a value that follows the line.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Parsed {
    Ready(Command),
    NeedsValue {
        key: String,
        len: usize,
        ttl: Option<Duration>,
        only_if_absent: bool,
    },
}

impl Parsed {
    pub fn with_value(self, value: Vec<u8>) -> Command {
        match self {
            Parsed::Ready(cmd) => cmd,
            Parsed::NeedsValue {
                key,
                ttl,
                only_if_absent,
                ..
            } => {
                if only_if_absent {
                    Command::SetNx { key, value }
                } else {
                    Command::Set { key, value, ttl }
                }
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProtocolError {
    Empty,
    UnknownCommand(String),
    WrongArity(String),
    BadNumber(String),
    KeyTooLong,
}

impl fmt::Display for ProtocolError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ProtocolError::Empty => f.write_str("empty command"),
            ProtocolError::UnknownCommand(name) => write!(f, "unknown command '{name}'"),
            ProtocolError::WrongArity(name) => write!(f, "wrong number of arguments for {name}"),
            ProtocolError::BadNumber(text) => write!(f, "not a valid number: {text}"),
            ProtocolError::KeyTooLong => write!(f, "key longer than {MAX_KEY_LEN} bytes"),
        }
    }
}

impl std::error::Error for ProtocolError {}

fn key(arg: &str) -> Result<String, ProtocolError> {
    if arg.len() > MAX_KEY_LEN {
        return Err(ProtocolError::KeyTooLong);
    }
    Ok(arg.to_string())
}

fn number<T: std::str::FromStr>(arg: &str) -> Result<T, ProtocolError> {
    arg.parse()
        .map_err(|_| ProtocolError::BadNumber(arg.to_string()))
}

fn ttl_secs(arg: &str) -> Result<Duration, ProtocolError> {
    let ttl = Duration::from_secs(number(arg)?);
    if ttl.is_zero() || ttl > MAX_TTL {
        return Err(ProtocolError::BadNumber(arg.to_string()));
    }
    Ok(ttl)
}

const COMMANDS: &[&str] = &[
    "PING", "AUTH", "GET", "SET", "SETNX", "DEL", "INCR", "EXPIRE", "TTL", "KEYS", "STATS", "SAVE",
    "BACKUP", "FLUSH", "QUIT",
];

/// Parse one command line (without the trailing `\r\n`).
pub fn parse_line(raw: &[u8]) -> Result<Parsed, ProtocolError> {
    let line = unsafe { std::str::from_utf8_unchecked(raw) };
    let mut parts = line.split_ascii_whitespace();
    let name = parts
        .next()
        .ok_or(ProtocolError::Empty)?
        .to_ascii_uppercase();
    let args: Vec<&str> = parts.collect();
    let ready = |cmd| Ok(Parsed::Ready(cmd));
    match (name.as_str(), args.as_slice()) {
        ("PING", []) => ready(Command::Ping),
        ("AUTH", [token]) => ready(Command::Auth(token.to_string())),
        ("GET", [k]) => ready(Command::Get(key(k)?)),
        ("SET", [k, len]) => Ok(Parsed::NeedsValue {
            key: key(k)?,
            len: number(len)?,
            ttl: None,
            only_if_absent: false,
        }),
        ("SET", [k, len, ex, secs]) if ex.eq_ignore_ascii_case("EX") => Ok(Parsed::NeedsValue {
            key: key(k)?,
            len: number(len)?,
            ttl: Some(ttl_secs(secs)?),
            only_if_absent: false,
        }),
        ("SETNX", [k, len]) => Ok(Parsed::NeedsValue {
            key: key(k)?,
            len: number(len)?,
            ttl: None,
            only_if_absent: true,
        }),
        ("DEL", [k]) => ready(Command::Del(key(k)?)),
        ("INCR", [k]) => ready(Command::Incr {
            key: key(k)?,
            delta: 1,
        }),
        ("INCR", [k, delta]) => ready(Command::Incr {
            key: key(k)?,
            delta: number(delta)?,
        }),
        ("EXPIRE", [k, secs]) => ready(Command::Expire {
            key: key(k)?,
            ttl: ttl_secs(secs)?,
        }),
        ("TTL", [k]) => ready(Command::Ttl(key(k)?)),
        ("KEYS", [prefix]) => ready(Command::Keys(prefix.to_string())),
        ("KEYS", []) => ready(Command::Keys(String::new())),
        ("STATS", []) => ready(Command::Stats),
        ("SAVE", []) => ready(Command::Save),
        ("BACKUP", [name]) => ready(Command::Backup(name.to_string())),
        ("FLUSH", []) => ready(Command::Flush),
        ("QUIT", []) => ready(Command::Quit),
        _ if COMMANDS.contains(&name.as_str()) => Err(ProtocolError::WrongArity(name)),
        _ => Err(ProtocolError::UnknownCommand(name)),
    }
}
