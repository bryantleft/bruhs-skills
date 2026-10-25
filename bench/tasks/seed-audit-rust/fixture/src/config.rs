use std::fmt;
use std::path::PathBuf;

pub const USAGE: &str = "usage: kvlite [--bind ADDR] [--port N] [--data-dir DIR] \
[--token TOKEN] [--max-keys N] [--max-connections N]";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub bind: String,
    pub port: u16,
    pub data_dir: PathBuf,
    pub token: Option<String>,
    pub max_keys: usize,
    pub max_connections: usize,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            bind: "127.0.0.1".to_string(),
            port: 7379,
            data_dir: PathBuf::from("./data"),
            token: None,
            max_keys: 100_000,
            max_connections: 256,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConfigError(pub String);

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for ConfigError {}

fn number<T: std::str::FromStr>(flag: &str, value: &str) -> Result<T, ConfigError> {
    value
        .parse()
        .map_err(|_| ConfigError(format!("{flag}: not a number: {value}")))
}

impl Config {
    pub fn from_args<I>(args: I) -> Result<Self, ConfigError>
    where
        I: IntoIterator<Item = String>,
    {
        let mut config = Config {
            token: std::env::var("KVLITE_TOKEN").ok().filter(|t| !t.is_empty()),
            ..Config::default()
        };
        let mut args = args.into_iter();
        while let Some(flag) = args.next() {
            let value = args
                .next()
                .ok_or_else(|| ConfigError(format!("{flag} needs a value")))?;
            match flag.as_str() {
                "--bind" => config.bind = value,
                "--port" => {
                    let port: u32 = number(&flag, &value)?;
                    config.port = port as u16;
                }
                "--data-dir" => config.data_dir = PathBuf::from(value),
                "--token" => config.token = Some(value).filter(|t| !t.is_empty()),
                "--max-keys" => config.max_keys = number(&flag, &value)?,
                "--max-connections" => config.max_connections = number(&flag, &value)?,
                other => return Err(ConfigError(format!("unknown flag {other}"))),
            }
        }
        if config.max_connections == 0 {
            return Err(ConfigError("--max-connections must be at least 1".into()));
        }
        Ok(config)
    }

    pub fn addr(&self) -> String {
        format!("{}:{}", self.bind, self.port)
    }
}
