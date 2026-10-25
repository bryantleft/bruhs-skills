use std::io::{BufRead, BufReader, Write};
use std::net::TcpStream;
use std::path::PathBuf;
use std::thread;

use kvlite::config::Config;
use kvlite::server::Server;

struct Client {
    reader: BufReader<TcpStream>,
    writer: TcpStream,
}

impl Client {
    fn connect(addr: std::net::SocketAddr) -> Client {
        let stream = TcpStream::connect(addr).unwrap();
        Client {
            reader: BufReader::new(stream.try_clone().unwrap()),
            writer: stream,
        }
    }

    fn send(&mut self, raw: &str) {
        self.writer.write_all(raw.as_bytes()).unwrap();
    }

    fn line(&mut self) -> String {
        let mut line = String::new();
        self.reader.read_line(&mut line).unwrap();
        line.trim_end().to_string()
    }

    fn call(&mut self, raw: &str) -> String {
        self.send(raw);
        self.line()
    }
}

fn start(token: Option<&str>, name: &str) -> std::net::SocketAddr {
    let data_dir: PathBuf =
        std::env::temp_dir().join(format!("kvlite-server-{name}-{}", std::process::id()));
    let config = Config {
        port: 0,
        data_dir,
        token: token.map(String::from),
        ..Config::default()
    };
    let server = Server::bind(Box::leak(Box::new(config))).unwrap();
    let addr = server.local_addr().unwrap();
    thread::spawn(move || server.run());
    addr
}

#[test]
fn set_get_del_over_tcp() {
    let mut c = Client::connect(start(None, "basic"));
    assert_eq!(c.call("PING\r\n"), "$4");
    assert_eq!(c.line(), "PONG");
    assert_eq!(c.call("SET greeting 5\r\nhello\r\n"), "+OK");
    assert_eq!(c.call("GET greeting\r\n"), "$5");
    assert_eq!(c.line(), "hello");
    assert_eq!(c.call("DEL greeting\r\n"), ":1");
    assert_eq!(c.call("GET greeting\r\n"), "$-1");
    assert_eq!(c.call("QUIT\r\n"), "+OK");
}

#[test]
fn counters_and_setnx() {
    let mut c = Client::connect(start(None, "counters"));
    assert_eq!(c.call("INCR visits\r\n"), ":1");
    assert_eq!(c.call("INCR visits 10\r\n"), ":11");
    assert_eq!(c.call("SETNX lock 1\r\na\r\n"), ":1");
    assert_eq!(c.call("SETNX lock 1\r\nb\r\n"), ":0");
    assert_eq!(c.call("GET lock\r\n"), "$1");
    assert_eq!(c.line(), "a");
}

#[test]
fn keys_lists_matches() {
    let mut c = Client::connect(start(None, "keys"));
    c.call("SET job:1 1\r\na\r\n");
    c.call("SET job:2 1\r\nb\r\n");
    c.call("SET user:1 1\r\nc\r\n");
    assert_eq!(c.call("KEYS job:\r\n"), "*2");
    assert_eq!(c.line(), "$5");
    assert_eq!(c.line(), "job:1");
    assert_eq!(c.line(), "$5");
    assert_eq!(c.line(), "job:2");
}

#[test]
fn token_required_for_data() {
    let mut c = Client::connect(start(Some("s3cret"), "auth"));
    assert!(c.call("GET k\r\n").starts_with("-ERR NOAUTH"));
    assert_eq!(c.call("AUTH wrong\r\n"), "-ERR invalid token");
    assert_eq!(c.call("AUTH s3cret\r\n"), "+OK");
    assert_eq!(c.call("GET k\r\n"), "$-1");
}

#[test]
fn protocol_errors_keep_the_connection() {
    let mut c = Client::connect(start(None, "errors"));
    assert_eq!(c.call("BOGUS\r\n"), "-ERR unknown command 'BOGUS'");
    assert_eq!(c.call("INCR a b\r\n"), "-ERR not a valid number: b");
    assert_eq!(c.call("PING\r\n"), "$4");
}
