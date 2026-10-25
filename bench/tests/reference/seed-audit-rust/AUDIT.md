# Audit: kvlite

Each finding is `### [severity] file:lines`.

## Security

### [critical] src/persist.rs:142-149
`BACKUP <name>` joins the client's name onto the data dir with no validation. `../x` or an
absolute path writes a snapshot anywhere the process can write. Accept `[A-Za-z0-9_-]+` only.

### [critical] src/protocol.rs:42-54
`requires_auth` omits `FLUSH`, `SAVE`, `BACKUP` and `STATS`. Without a token anyone can wipe
the store or write backup files. Invert it: everything except `PING`/`AUTH`/`QUIT`.

### [high] src/protocol.rs:144
`from_utf8_unchecked` on bytes straight off the socket: a client sending invalid UTF-8 causes
undefined behaviour. Use `std::str::from_utf8` and return a protocol error.

### [high] src/server.rs:84-85
The SET/SETNX length is trusted: `vec![0u8; len]` allocates whatever the client claims, so
`SET k 1099511627776` aborts the process. Enforce a maximum value size.

## Correctness

### [high] src/store.rs:12-14
`is_expired` is inverted (`deadline > now`): TTL keys vanish immediately and come back once
the deadline passes, then never expire.

### [high] src/server.rs:235-239
`INCR` on a non-integer value hits `.expect()` while holding the store mutex. The thread
panics, the mutex is poisoned, and every other connection then panics on `lock().unwrap()`.
Return `-ERR` instead.

### [medium] src/server.rs:223-228
`SETNX` checks and sets under two separate locks, so two clients can both acquire the "lock".
Do both under one guard.

### [medium] src/store.rs:127
`current + delta` overflows: panic in debug builds, silent wrap in release. Use `checked_add`.

### [low] src/config.rs:64-65
`--port` is parsed as `u32` and truncated with `as u16`; `--port 70000` listens on 4464.

## Error handling

### [high] src/server.rs:126-131
Nothing ever snapshots on its own: no periodic `SAVE` (the README promises periodic
snapshots) and none on shutdown. Everything since the last manual `SAVE` is lost on restart
or crash. Add a timer thread that renders and saves, and save on SIGTERM.

### [high] src/persist.rs:127-130
A corrupt snapshot (`unwrap_or_default`) or an unreadable one starts the server empty and
silent, and the next `SAVE` overwrites the real data. Fail loudly on anything but not-found.

### [medium] src/persist.rs:155-158
`let _ = out.flush()` drops the error where buffered writes actually fail, so `SAVE` replies
`+OK` for a truncated file. It also truncates `dump.snap` in place; write a temp file and
rename.

## Performance

### [medium] src/server.rs:210-211
`GET` clones the whole store under the lock to read one key.

### [medium] src/server.rs:60-80
`read_line` issues one `read()` syscall per byte on the raw socket. Use a `BufReader`.

### [medium] src/server.rs:250-257
`KEYS` writes to the socket while holding the global store lock; a slow client stalls
everyone. Collect the keys, drop the guard, then write.

### [medium] src/stats.rs:12-30
Every latency is kept forever, and `STATS` clones and sorts the whole vector. Use a ring
buffer or a histogram.
