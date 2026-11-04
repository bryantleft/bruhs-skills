#!/usr/bin/env bash
# Rust Axum ride-pricing service with disciplined test infra:
#   .github/workflows/ci.yml   fmt, clippy --all-targets -D warnings (tests
#                              included), cargo nextest + llvm-cov with
#                              diff-cover --fail-under=85 on changed lines,
#                              scripts/check_deps.sh against
#                              dependency-rules.json, and an acceptance job
#                              (docker compose + acceptance/run.sh specs).
#                              No continue-on-error anywhere.
#   .github/workflows/mutants.yml  weekly cargo mutants with a ratchet against
#                              mutants-baseline.json, chosen deliberately in
#                              docs/adr/0003-weekly-mutation-ratchet.md.
# Absent: the complexity composite. src/pricing/fare.rs::quote() is a nested
# branchy hotspot with two recent bug-fix commits and unit tests on only a
# few branches, so there is a concrete thing that layer would surface.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# eval_state, but writes the "no rules" placeholder when the stack derives no
# rules (sync_bruhs_block.py rejects the empty stdin eval_state pipes it).
eval_repo
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "axum", "language": "rust", "libraries": ["tokio", "sqlx"], "testing": ["cargo-nextest", "cargo-mutants"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write Cargo.toml <<'EOF'
[package]
name = "fares"
version = "0.9.0"
edition = "2021"

[dependencies]
axum = "0.8"
serde = { version = "1", features = ["derive"] }
sqlx = { version = "0.8", features = ["runtime-tokio", "postgres"] }
tokio = { version = "1", features = ["full"] }

[dev-dependencies]
tower = { version = "0.5", features = ["util"] }
EOF

eval_write .gitignore <<'EOF'
target/
lcov.info
mutants.out/
EOF

eval_write rustfmt.toml <<'EOF'
edition = "2021"
max_width = 100
EOF

eval_write clippy.toml <<'EOF'
# Applies to every target, tests included (CI runs clippy --all-targets).
disallowed-methods = [{ path = "std::thread::sleep", reason = "use tokio::time::sleep" }]
EOF

eval_write .config/nextest.toml <<'EOF'
[profile.ci]
fail-fast = false
retries = 0
slow-timeout = { period = "30s", terminate-after = 2 }
EOF

eval_write dependency-rules.json <<'EOF'
{
  "description": "Module layering. domain is pure; routes may use domain and db; db may use domain.",
  "rules": [
    { "from": "pricing", "forbid": ["routes", "db"] },
    { "from": "db", "forbid": ["routes"] }
  ]
}
EOF

eval_write scripts/check_deps.sh <<'EOF'
#!/usr/bin/env bash
# Fails when a module imports a module dependency-rules.json forbids.
set -euo pipefail
status=0
while IFS=$'\t' read -r from forbid; do
  paths=()
  for p in "src/${from}.rs" "src/${from}"; do [ -e "$p" ] && paths+=("$p"); done
  if [ ${#paths[@]} -eq 0 ]; then
    echo "dependency-rules.json names module '${from}', but there is no src/${from}.rs or src/${from}/" >&2
    exit 1
  fi
  if grep -rnE "use crate::(${forbid})\b" "${paths[@]}"; then
    echo "dependency rule violated: src/${from} must not import crate::{${forbid//|/,}}" >&2
    status=1
  fi
done < <(python3 -c 'import json; [print(r["from"], "|".join(r["forbid"]), sep="\t") for r in json.load(open("dependency-rules.json"))["rules"]]')
exit $status
EOF
chmod +x scripts/check_deps.sh

eval_write src/main.rs <<'EOF'
use fares::{db, routes};

#[tokio::main]
async fn main() {
    let pool = db::connect().await.expect("DATABASE_URL must point at a reachable Postgres");
    let app = routes::router(pool);
    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
EOF

eval_write src/db.rs <<'EOF'
use sqlx::PgPool;

pub async fn connect() -> Result<PgPool, sqlx::Error> {
    let url = std::env::var("DATABASE_URL").expect("DATABASE_URL is not set");
    PgPool::connect(&url).await
}

pub async fn surge_multiplier(pool: &PgPool, zone: &str) -> Result<f64, sqlx::Error> {
    sqlx::query_scalar("select multiplier from surge where zone = $1")
        .bind(zone)
        .fetch_optional(pool)
        .await
        .map(|m| m.unwrap_or(1.0))
}
EOF

eval_write src/routes.rs <<'EOF'
use axum::{extract::State, routing::post, Json, Router};
use serde::Deserialize;
use sqlx::PgPool;

use crate::db;
use crate::pricing::fare::{quote, Ride};

#[derive(Deserialize)]
pub struct QuoteRequest {
    pub zone: String,
    pub ride: Ride,
}

pub fn router(pool: PgPool) -> Router {
    Router::new().route("/quote", post(quote_handler)).with_state(pool)
}

async fn quote_handler(State(pool): State<PgPool>, Json(req): Json<QuoteRequest>) -> Json<u32> {
    let surge = db::surge_multiplier(&pool, &req.zone).await.unwrap_or(1.0);
    Json(quote(&req.ride, surge))
}
EOF

eval_write src/pricing/mod.rs <<'EOF'
pub mod fare;
EOF

eval_write src/pricing/fare.rs <<'EOF'
use serde::Deserialize;

#[derive(Deserialize, Clone, Copy, PartialEq)]
pub enum Tier {
    Standard,
    Xl,
    Black,
}

#[derive(Deserialize)]
pub struct Ride {
    pub tier: Tier,
    pub km: f64,
    pub minutes: f64,
    pub airport_pickup: bool,
    pub airport_dropoff: bool,
    pub night: bool,
    pub promo_percent: Option<u8>,
}

/// Fare in cents.
pub fn quote(ride: &Ride, surge: f64) -> u32 {
    let (base, per_km, per_min) = match ride.tier {
        Tier::Standard => (250.0, 110.0, 25.0),
        Tier::Xl => (400.0, 165.0, 35.0),
        Tier::Black => (700.0, 260.0, 55.0),
    };
    let mut fare = base + per_km * ride.km + per_min * ride.minutes;

    if ride.airport_pickup || ride.airport_dropoff {
        if ride.airport_pickup && ride.airport_dropoff {
            fare += 600.0;
        } else if ride.airport_pickup {
            fare += if ride.tier == Tier::Black { 0.0 } else { 450.0 };
        } else {
            fare += 300.0;
        }
    }

    if surge > 1.0 {
        if ride.airport_pickup && ride.tier != Tier::Black {
            fare *= surge.min(1.5);
        } else if ride.night {
            fare *= surge.min(2.0);
        } else {
            fare *= surge;
        }
    } else if ride.night && ride.tier == Tier::Standard {
        fare *= 1.1;
    }

    if let Some(p) = ride.promo_percent {
        if p > 0 && p <= 50 && !(ride.airport_pickup && surge > 1.0) {
            fare -= fare * f64::from(p) / 100.0;
        }
    }

    let minimum = match ride.tier {
        Tier::Standard => 700.0,
        Tier::Xl => 1000.0,
        Tier::Black => 1800.0,
    };
    fare.max(minimum).round() as u32
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ride(tier: Tier) -> Ride {
        Ride { tier, km: 10.0, minutes: 20.0, airport_pickup: false, airport_dropoff: false, night: false, promo_percent: None }
    }

    #[test]
    fn standard_daytime_fare() {
        assert_eq!(quote(&ride(Tier::Standard), 1.0), 1850);
    }

    #[test]
    fn minimum_fare_applies() {
        let short = Ride { km: 0.5, minutes: 2.0, ..ride(Tier::Black) };
        assert_eq!(quote(&short, 1.0), 1800);
    }
}
EOF

eval_write tests/api.rs <<'EOF'
// Contract test for the /quote request shape; runs against the router with a
// lazily connected pool, so it never touches Postgres.
use axum::body::Body;
use axum::http::{Request, StatusCode};
use tower::ServiceExt;

#[tokio::test]
async fn rejects_a_malformed_quote_request() {
    let pool = sqlx::PgPool::connect_lazy("postgres://unused@localhost/unused").unwrap();
    let app = fares::routes::router(pool);
    let res = app
        .oneshot(Request::post("/quote").header("content-type", "application/json").body(Body::from("{}")).unwrap())
        .await
        .unwrap();
    assert_eq!(res.status(), StatusCode::UNPROCESSABLE_ENTITY);
}
EOF

eval_write src/lib.rs <<'EOF'
pub mod db;
pub mod pricing;
pub mod routes;
EOF

eval_write docker-compose.yml <<'EOF'
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_PASSWORD: fares
    ports: ["5432:5432"]
  app:
    build: .
    environment:
      DATABASE_URL: postgres://postgres:fares@db:5432/postgres
    ports: ["8080:8080"]
    depends_on: [db]
EOF

eval_write acceptance/run.sh <<'EOF'
#!/usr/bin/env bash
# Runs every acceptance/specs/*.sh against the composed stack. Each spec is a
# scenario: Given (seed SQL) / When (HTTP call) / Then (assert on the body).
set -euo pipefail
export BASE_URL="${BASE_URL:-http://localhost:8080}"
failed=0
for spec in acceptance/specs/*.sh; do
  if bash "$spec"; then echo "PASS $spec"; else echo "FAIL $spec"; failed=1; fi
done
exit $failed
EOF
chmod +x acceptance/run.sh

eval_write acceptance/specs/standard-quote.sh <<'EOF'
# Scenario: a rider in a calm zone gets the standard daytime fare.
set -euo pipefail
psql "$DATABASE_URL" -qc "delete from surge where zone = 'downtown'"
body=$(curl -sf "$BASE_URL/quote" -H 'content-type: application/json' \
  -d '{"zone":"downtown","ride":{"tier":"Standard","km":10,"minutes":20,"airport_pickup":false,"airport_dropoff":false,"night":false,"promo_percent":null}}')
[ "$body" = "1850" ]
EOF

eval_write acceptance/specs/surge-capped-at-airport.sh <<'EOF'
# Scenario: surge at an airport pickup is capped at 1.5x for non-Black tiers.
set -euo pipefail
psql "$DATABASE_URL" -qc "insert into surge (zone, multiplier) values ('sfo', 3.0) on conflict (zone) do update set multiplier = 3.0"
body=$(curl -sf "$BASE_URL/quote" -H 'content-type: application/json' \
  -d '{"zone":"sfo","ride":{"tier":"Standard","km":10,"minutes":20,"airport_pickup":true,"airport_dropoff":false,"night":false,"promo_percent":null}}')
[ "$body" = "3450" ]
EOF

eval_write .github/workflows/ci.yml <<'EOF'
name: ci

on:
  pull_request:
  push:
    branches: [main]

jobs:
  fmt:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cargo fmt --all --check

  clippy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cargo clippy --all-targets -- -D warnings

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: taiki-e/install-action@v2
        with:
          tool: cargo-nextest,cargo-llvm-cov
      - run: cargo llvm-cov nextest --profile ci --lcov --output-path lcov.info
      - name: Coverage on changed lines
        run: pipx run diff-cover lcov.info --compare-branch=origin/main --fail-under=85

  architecture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Dependency rules
        run: scripts/check_deps.sh

  acceptance:
    runs-on: ubuntu-latest
    needs: [test]
    steps:
      - uses: actions/checkout@v4
      - run: docker compose up -d --build --wait
      - run: acceptance/run.sh
        env:
          DATABASE_URL: postgres://postgres:fares@localhost:5432/postgres
EOF

eval_write .github/workflows/mutants.yml <<'EOF'
name: mutants

on:
  schedule:
    - cron: "0 6 * * 1"
  workflow_dispatch:

jobs:
  mutants:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: taiki-e/install-action@v2
        with:
          tool: cargo-mutants
      - run: cargo mutants --no-shuffle --output mutants.out
      - name: Ratchet against baseline
        run: |
          caught=$(jq '.caught' mutants.out/outcomes.json)
          total=$(jq '.total_mutants' mutants.out/outcomes.json)
          ratio=$(python3 -c "print(round($caught / $total, 3))")
          floor=$(jq '.kill_ratio' mutants-baseline.json)
          echo "kill ratio $ratio (baseline $floor)"
          python3 -c "import sys; sys.exit(0 if $ratio >= $floor else 1)" \
            || { echo "kill ratio $ratio fell below baseline $floor"; exit 1; }
EOF

eval_write mutants-baseline.json <<'EOF'
{ "kill_ratio": 0.81, "updated": "2026-10-26", "note": "raise when the weekly run beats it; never lower" }
EOF

eval_write docs/adr/0003-weekly-mutation-ratchet.md <<'EOF'
# 3. Mutation testing runs weekly with a ratchet

Status: accepted

A full `cargo mutants` run takes about 50 minutes, longer than our PR budget.
We run it weekly and fail the run if the kill ratio drops below
mutants-baseline.json; the baseline only goes up. Per-PR mutation was tried for
a month and dropped for latency, not for value.
EOF

eval_commit "feat: fare quotes with layered CI"

python3 - <<'PY'
from pathlib import Path
p = Path("src/pricing/fare.rs")
s = p.read_text()
s = s.replace("            fare += 600.0;", "            fare += 600.0; // both ends: one combined airport fee")
p.write_text(s)
PY
git add -A
git commit -q -m "fix: airport fee charged twice for airport-to-airport rides" -m "Pickup and dropoff fees were both added when a ride started and ended at an airport. Charge one combined fee."

python3 - <<'PY'
from pathlib import Path
p = Path("src/pricing/fare.rs")
s = p.read_text()
s = s.replace("if p > 0 && p <= 50 && !(ride.airport_pickup && surge > 1.0) {", "if p > 0 && p <= 50 && !(ride.airport_pickup && surge > 1.0) {\n            // promos never stack with capped airport surge")
p.write_text(s)
PY
git add -A
git commit -q -m "fix: promo applied on top of capped airport surge" -m "A promo on a surged airport pickup took the fare below the minimum the airport contract requires."

eval_origin
eval_gh
