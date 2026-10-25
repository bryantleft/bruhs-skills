use std::fmt::Write as _;
use std::time::Duration;

#[derive(Debug, Default)]
pub struct Stats {
    commands: u64,
    errors: u64,
    latencies_us: Vec<u64>,
}

impl Stats {
    pub fn record(&mut self, elapsed: Duration, ok: bool) {
        self.commands += 1;
        if !ok {
            self.errors += 1;
        }
        self.latencies_us
            .push(elapsed.as_micros().min(u64::MAX as u128) as u64);
    }

    pub fn commands(&self) -> u64 {
        self.commands
    }

    pub fn percentile(&self, p: f64) -> Option<u64> {
        if self.latencies_us.is_empty() {
            return None;
        }
        let mut sorted = self.latencies_us.clone();
        sorted.sort_unstable();
        let rank = ((p / 100.0) * (sorted.len() - 1) as f64).round() as usize;
        Some(sorted[rank.min(sorted.len() - 1)])
    }

    pub fn render(&self, keys: usize, connections: usize) -> String {
        let mut out = String::new();
        writeln!(out, "keys:{keys}").unwrap();
        writeln!(out, "connections:{connections}").unwrap();
        writeln!(out, "commands:{}", self.commands).unwrap();
        writeln!(out, "errors:{}", self.errors).unwrap();
        for p in [50.0, 99.0] {
            match self.percentile(p) {
                Some(us) => writeln!(out, "p{p}_us:{us}").unwrap(),
                None => writeln!(out, "p{p}_us:-").unwrap(),
            }
        }
        out
    }
}
