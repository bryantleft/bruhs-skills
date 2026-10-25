use std::time::Duration;

use kvlite::protocol::{parse_line, Command, Parsed, ProtocolError};

fn ready(line: &str) -> Command {
    match parse_line(line.as_bytes()) {
        Ok(Parsed::Ready(cmd)) => cmd,
        other => panic!("{line}: {other:?}"),
    }
}

#[test]
fn simple_commands() {
    assert_eq!(ready("PING"), Command::Ping);
    assert_eq!(ready("get user:1"), Command::Get("user:1".into()));
    assert_eq!(ready("DEL k"), Command::Del("k".into()));
    assert_eq!(
        ready("INCR k"),
        Command::Incr {
            key: "k".into(),
            delta: 1
        }
    );
    assert_eq!(
        ready("INCR k -3"),
        Command::Incr {
            key: "k".into(),
            delta: -3
        }
    );
    assert_eq!(ready("KEYS"), Command::Keys(String::new()));
    assert_eq!(
        ready("EXPIRE k 30"),
        Command::Expire {
            key: "k".into(),
            ttl: Duration::from_secs(30)
        }
    );
}

#[test]
fn set_announces_a_value() {
    let parsed = parse_line(b"SET greeting 5 EX 60").unwrap();
    assert_eq!(
        parsed,
        Parsed::NeedsValue {
            key: "greeting".into(),
            len: 5,
            ttl: Some(Duration::from_secs(60)),
            only_if_absent: false,
        }
    );
    assert_eq!(
        parsed.with_value(b"hello".to_vec()),
        Command::Set {
            key: "greeting".into(),
            value: b"hello".to_vec(),
            ttl: Some(Duration::from_secs(60)),
        }
    );
}

#[test]
fn setnx_announces_a_value() {
    let parsed = parse_line(b"SETNX lock 1").unwrap();
    assert_eq!(
        parsed.with_value(b"x".to_vec()),
        Command::SetNx {
            key: "lock".into(),
            value: b"x".to_vec()
        }
    );
}

#[test]
fn errors() {
    assert_eq!(parse_line(b""), Err(ProtocolError::Empty));
    assert_eq!(
        parse_line(b"NOPE"),
        Err(ProtocolError::UnknownCommand("NOPE".into()))
    );
    assert_eq!(
        parse_line(b"GET"),
        Err(ProtocolError::WrongArity("GET".into()))
    );
    assert!(matches!(
        parse_line(b"INCR k abc"),
        Err(ProtocolError::BadNumber(_))
    ));
    assert!(matches!(
        parse_line(b"EXPIRE k 0"),
        Err(ProtocolError::BadNumber(_))
    ));
    let long_key = format!("GET {}", "k".repeat(600));
    assert_eq!(
        parse_line(long_key.as_bytes()),
        Err(ProtocolError::KeyTooLong)
    );
}

#[test]
fn data_commands_need_auth() {
    assert!(ready("GET k").requires_auth());
    assert!(ready("DEL k").requires_auth());
    assert!(!ready("PING").requires_auth());
    assert!(!ready("AUTH secret").requires_auth());
}
