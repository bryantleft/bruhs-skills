# kvlite

A small in-memory key-value server for internal tooling (feature flags, rate-limit
counters, job locks). One process, one global map, periodic snapshots to disk. No
dependencies beyond `std`.

## Running

```sh
cargo run --release -- --port 7379 --data-dir ./data --token "$KVLITE_TOKEN"
```

| Flag | Default | |
|---|---|---|
| `--bind` | `127.0.0.1` | |
| `--port` | `7379` | |
| `--data-dir` | `./data` | snapshots and backups live here |
| `--token` | `$KVLITE_TOKEN` | clients must `AUTH` with it before touching data; unset = no auth |
| `--max-keys` | `100000` | |
| `--max-connections` | `256` | |

## Protocol

Line based, `\r\n` terminated. Values are length-prefixed: the command line carries the
byte length and the value follows on the next line.

```
AUTH <token>
PING
GET <key>
SET <key> <len> [EX <seconds>]     then <len> bytes, then \r\n
SETNX <key> <len>                  then <len> bytes, then \r\n
DEL <key>
INCR <key> [delta]
EXPIRE <key> <seconds>
KEYS <prefix>
STATS
SAVE                               snapshot to <data-dir>/dump.snap
BACKUP <name>                      snapshot to <data-dir>/<name>.snap
FLUSH                              drop every key
QUIT
```

Replies: `+OK`, `:<int>`, `$<len>` + bytes, `$-1` (nil), `*<n>` + n bulk strings,
`-ERR <message>`.

Everything except `PING`, `AUTH` and `QUIT` needs a successful `AUTH` when a token is set.

## Tests

```sh
cargo test
```
