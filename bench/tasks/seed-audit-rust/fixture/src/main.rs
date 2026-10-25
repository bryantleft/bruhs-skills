use std::process::ExitCode;

use kvlite::config::{Config, USAGE};
use kvlite::server::Server;

fn main() -> ExitCode {
    let config = match Config::from_args(std::env::args().skip(1)) {
        Ok(config) => config,
        Err(err) => {
            eprintln!("kvlite: {err}\n{USAGE}");
            return ExitCode::from(2);
        }
    };
    let config: &'static Config = Box::leak(Box::new(config));

    let server = match Server::bind(config) {
        Ok(server) => server,
        Err(err) => {
            eprintln!("kvlite: cannot start on {}: {err}", config.addr());
            return ExitCode::FAILURE;
        }
    };
    match server.local_addr() {
        Ok(addr) => eprintln!("kvlite listening on {addr}"),
        Err(err) => eprintln!("kvlite listening (address unknown: {err})"),
    }
    if let Err(err) = server.run() {
        eprintln!("kvlite: {err}");
        return ExitCode::FAILURE;
    }
    ExitCode::SUCCESS
}
