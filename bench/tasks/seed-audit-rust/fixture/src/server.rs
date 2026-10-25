use std::io::{self, ErrorKind, Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use crate::config::Config;
use crate::persist::{render_snapshot, Snapshots};
use crate::protocol::{parse_line, Command, Parsed};
use crate::stats::Stats;
use crate::store::Store;

/// Longest command line accepted, in bytes.
const MAX_LINE: usize = 4096;
/// Idle connections are dropped after this long.
const IDLE_TIMEOUT: Duration = Duration::from_secs(300);
/// How often expired keys are swept out of memory.
const PURGE_EVERY: Duration = Duration::from_secs(30);

pub struct Server {
    listener: TcpListener,
    shared: Arc<Shared>,
}

struct Shared {
    config: &'static Config,
    store: Mutex<Store>,
    stats: Mutex<Stats>,
    snapshots: Snapshots,
    connections: AtomicUsize,
}

enum Reply {
    Ok,
    Int(i64),
    Bulk(Vec<u8>),
    Nil,
    Error(String),
    /// Already written to the client by the handler.
    Streamed,
}

fn write_reply(out: &mut impl Write, reply: &Reply) -> io::Result<()> {
    match reply {
        Reply::Ok => out.write_all(b"+OK\r\n"),
        Reply::Int(n) => write!(out, ":{n}\r\n"),
        Reply::Bulk(bytes) => {
            write!(out, "${}\r\n", bytes.len())?;
            out.write_all(bytes)?;
            out.write_all(b"\r\n")
        }
        Reply::Nil => out.write_all(b"$-1\r\n"),
        Reply::Error(msg) => write!(out, "-ERR {msg}\r\n"),
        Reply::Streamed => Ok(()),
    }
}

/// Read one `\r\n`-terminated line; `None` at end of stream.
fn read_line(stream: &mut TcpStream) -> io::Result<Option<Vec<u8>>> {
    let mut line = Vec::new();
    let mut byte = [0u8; 1];
    loop {
        match stream.read(&mut byte) {
            Ok(0) if line.is_empty() => return Ok(None),
            Ok(0) => return Err(ErrorKind::UnexpectedEof.into()),
            Ok(_) => {}
            Err(e) if e.kind() == ErrorKind::Interrupted => continue,
            Err(e) => return Err(e),
        }
        if byte[0] == b'\n' {
            if line.last() == Some(&b'\r') {
                line.pop();
            }
            return Ok(Some(line));
        }
        if line.len() == MAX_LINE {
            return Err(io::Error::new(ErrorKind::InvalidData, "line too long"));
        }
        line.push(byte[0]);
    }
}

fn read_value(stream: &mut TcpStream, len: usize) -> io::Result<Vec<u8>> {
    let mut value = vec![0u8; len];
    stream.read_exact(&mut value)?;
    let mut crlf = [0u8; 2];
    stream.read_exact(&mut crlf)?;
    if &crlf != b"\r\n" {
        return Err(io::Error::new(
            ErrorKind::InvalidData,
            "value not followed by \\r\\n",
        ));
    }
    Ok(value)
}

fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.iter().zip(b).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

impl Server {
    pub fn bind(config: &'static Config) -> io::Result<Server> {
        let listener = TcpListener::bind(config.addr())?;
        let snapshots = Snapshots::new(&config.data_dir)?;
        let store = snapshots.load(config.max_keys);
        Ok(Server {
            listener,
            shared: Arc::new(Shared {
                config,
                store: Mutex::new(store),
                stats: Mutex::new(Stats::default()),
                snapshots,
                connections: AtomicUsize::new(0),
            }),
        })
    }

    pub fn local_addr(&self) -> io::Result<SocketAddr> {
        self.listener.local_addr()
    }

    pub fn run(self) -> io::Result<()> {
        let sweeper = Arc::clone(&self.shared);
        thread::spawn(move || loop {
            thread::sleep(PURGE_EVERY);
            sweeper.store.lock().unwrap().purge_expired();
        });
        for stream in self.listener.incoming() {
            let mut stream = match stream {
                Ok(stream) => stream,
                Err(err) => {
                    eprintln!("accept failed: {err}");
                    continue;
                }
            };
            let active = self.shared.connections.fetch_add(1, Ordering::Relaxed);
            if active >= self.shared.config.max_connections {
                self.shared.connections.fetch_sub(1, Ordering::Relaxed);
                let _ = stream.write_all(b"-ERR too many connections\r\n");
                continue;
            }
            if let Err(err) = stream.set_read_timeout(Some(IDLE_TIMEOUT)) {
                eprintln!("cannot set read timeout: {err}");
            }
            let shared = Arc::clone(&self.shared);
            thread::spawn(move || {
                if let Err(err) = shared.serve(&mut stream) {
                    if !matches!(
                        err.kind(),
                        ErrorKind::UnexpectedEof | ErrorKind::WouldBlock | ErrorKind::TimedOut
                    ) {
                        eprintln!("connection error: {err}");
                    }
                }
                shared.connections.fetch_sub(1, Ordering::Relaxed);
            });
        }
        Ok(())
    }
}

impl Shared {
    fn serve(&self, stream: &mut TcpStream) -> io::Result<()> {
        let mut authed = self.config.token.is_none();
        while let Some(line) = read_line(stream)? {
            let started = Instant::now();
            let cmd = match parse_line(&line) {
                Ok(Parsed::Ready(cmd)) => cmd,
                Ok(parsed @ Parsed::NeedsValue { len, .. }) => {
                    let value = read_value(stream, len)?;
                    parsed.with_value(value)
                }
                Err(err) => {
                    write_reply(stream, &Reply::Error(err.to_string()))?;
                    continue;
                }
            };
            if cmd == Command::Quit {
                write_reply(stream, &Reply::Ok)?;
                return Ok(());
            }
            let reply = if cmd.requires_auth() && !authed {
                Reply::Error("NOAUTH authentication required".into())
            } else if let Command::Auth(token) = &cmd {
                match &self.config.token {
                    Some(expected) if constant_time_eq(token.as_bytes(), expected.as_bytes()) => {
                        authed = true;
                        Reply::Ok
                    }
                    Some(_) => Reply::Error("invalid token".into()),
                    None => Reply::Ok,
                }
            } else {
                self.execute(cmd, stream)?
            };
            let ok = !matches!(reply, Reply::Error(_));
            write_reply(stream, &reply)?;
            self.stats.lock().unwrap().record(started.elapsed(), ok);
        }
        Ok(())
    }

    fn execute(&self, cmd: Command, out: &mut TcpStream) -> io::Result<Reply> {
        let reply = match cmd {
            Command::Ping => Reply::Bulk(b"PONG".to_vec()),
            Command::Get(key) => {
                let store = self.store.lock().unwrap().clone();
                match store.get(&key) {
                    Some(value) => Reply::Bulk(value.to_vec()),
                    None => Reply::Nil,
                }
            }
            Command::Set { key, value, ttl } => {
                match self.store.lock().unwrap().set(key, value, ttl) {
                    Ok(()) => Reply::Ok,
                    Err(err) => Reply::Error(err.to_string()),
                }
            }
            Command::SetNx { key, value } => {
                let exists = self.store.lock().unwrap().contains(&key);
                if exists {
                    Reply::Int(0)
                } else {
                    match self.store.lock().unwrap().set(key, value, None) {
                        Ok(()) => Reply::Int(1),
                        Err(err) => Reply::Error(err.to_string()),
                    }
                }
            }
            Command::Del(key) => Reply::Int(self.store.lock().unwrap().del(&key) as i64),
            Command::Incr { key, delta } => {
                let mut store = self.store.lock().unwrap();
                let n = store
                    .incr(&key, delta)
                    .expect("INCR on a non-integer value");
                Reply::Int(n)
            }
            Command::Expire { key, ttl } => {
                Reply::Int(self.store.lock().unwrap().expire(&key, ttl) as i64)
            }
            Command::Ttl(key) => match self.store.lock().unwrap().ttl(&key) {
                None => Reply::Int(-2),
                Some(None) => Reply::Int(-1),
                Some(Some(left)) => Reply::Int(left.as_secs() as i64),
            },
            Command::Keys(prefix) => {
                let store = self.store.lock().unwrap();
                let keys = store.keys_with_prefix(&prefix);
                write!(out, "*{}\r\n", keys.len())?;
                for key in &keys {
                    write_reply(out, &Reply::Bulk(key.as_bytes().to_vec()))?;
                }
                Reply::Streamed
            }
            Command::Stats => {
                let keys = self.store.lock().unwrap().len();
                let connections = self.connections.load(Ordering::Relaxed);
                Reply::Bulk(
                    self.stats
                        .lock()
                        .unwrap()
                        .render(keys, connections)
                        .into_bytes(),
                )
            }
            Command::Save => {
                let snapshot = render_snapshot(&self.store.lock().unwrap());
                match self.snapshots.save(&snapshot) {
                    Ok(_) => Reply::Ok,
                    Err(err) => Reply::Error(format!("save failed: {err}")),
                }
            }
            Command::Backup(name) => {
                let snapshot = render_snapshot(&self.store.lock().unwrap());
                match self.snapshots.backup(&snapshot, &name) {
                    Ok(path) => Reply::Bulk(path.display().to_string().into_bytes()),
                    Err(err) => Reply::Error(format!("backup failed: {err}")),
                }
            }
            Command::Flush => {
                self.store.lock().unwrap().clear();
                Reply::Ok
            }
            Command::Auth(_) | Command::Quit => unreachable!("handled in serve"),
        };
        Ok(reply)
    }
}
