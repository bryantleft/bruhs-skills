# GPUI Patterns

Best practices for GPUI (Zed's UI framework). Loaded by `cook` and `slop` when `gpui` is in `Cargo.toml`.

> GPUI runs on a single foreground UI thread with a background executor for heavy work. State lives in `Entity<T>` handles. Updates are scoped through `Context<T>` and produce reactive notifications. Misuse causes panics, deadlocks, or retain cycles.

---

## The Mental Model

| Concept | Type | Notes |
|---------|------|-------|
| Reference to UI state | `Entity<T>` | Strong handle, ref-counted, runs on UI thread |
| Weak reference | `WeakEntity<T>` | Doesn't keep entity alive; `.update` returns `Result` |
| Context for an entity | `Context<T>` (`&mut`) | Enters scope of one entity for updates |
| App context | `App` (`&mut`) | Top-level — create entities, no specific scope |
| Window context | `Window` | Per-window state; rendering and focus |
| Async context | `AsyncApp` | Used inside `cx.spawn`'d futures |

**Rules of the road:**
1. Entity state lives on the UI thread. All `update`/`read` calls happen there.
2. Mutating an entity requires its `Context<T>`.
3. Inside `entity.update(cx, |state, inner_cx| { ... })`, **use `inner_cx`**, not the outer `cx`.
4. **Closures hold `WeakEntity`**, not `Entity`, to avoid retain cycles.

---

## Creating Entities

```rust
// In an App context (top-level setup)
let counter = cx.new(|_cx| Counter { count: 0 });

// In another entity's setup
struct Parent { child: Entity<Child> }

impl Parent {
    fn new(cx: &mut App) -> Entity<Self> {
        cx.new(|cx| {
            let child = cx.new(|_| Child::default());
            Self { child }
        })
    }
}
```

---

## Reading and Updating

```rust
// Read — borrowed access
let count = counter.read(cx).count;
let name_len = counter.read_with(cx, |state, _cx| state.name.len());

// Update — mutable access, can call cx.notify() to trigger re-render
counter.update(cx, |state, cx| {
    state.count += 1;
    cx.notify();
});

// Update returning a value
let new_value = counter.update(cx, |state, cx| {
    state.count += 1;
    cx.notify();
    state.count
});
```

### Always use the inner `cx`

```rust
// ❌ Borrows cx twice — panic
counter.update(cx, |state, _inner_cx| {
    state.count += 1;
    cx.notify();  // outer cx — already borrowed by update
});

// ✅ Use the closure's cx
counter.update(cx, |state, inner_cx| {
    state.count += 1;
    inner_cx.notify();
});
```

### Don't nest updates

```rust
// ❌ Nested updates panic — entity is already locked
entity_a.update(cx, |a, cx| {
    entity_b.update(cx, |b, cx| { /* ... */ });
});

// ✅ Sequential
entity_a.update(cx, |a, cx| { /* ... */ });
entity_b.update(cx, |b, cx| { /* ... */ });

// ✅ Or compute outside, then apply
let value = entity_b.read(cx).value;
entity_a.update(cx, |a, cx| {
    a.adjusted = value * 2;
    cx.notify();
});
```

---

## Weak References — Always in Closures

`Entity<T>` is reference-counted. Capturing one inside a long-lived closure (event handlers, async tasks, observers) creates a cycle that prevents cleanup.

```rust
// ❌ Strong reference captured — retain cycle
impl MyView {
    fn setup(&mut self, cx: &mut Context<Self>) {
        let strong = cx.entity();
        register_callback(move || {
            strong.update(cx, |state, cx| { /* ... */ });
            //  ↑ this closure holds the entity, the entity holds this closure
        });
    }
}

// ✅ WeakEntity — doesn't keep alive
impl MyView {
    fn setup(&mut self, cx: &mut Context<Self>) {
        let weak = cx.entity().downgrade();
        register_callback(move |cx| {
            let _ = weak.update(cx, |state, cx| {
                state.ticked = true;
                cx.notify();
            });
        });
    }
}
```

`weak.update(cx, |...|)` returns `Result<R, _>` — `Err` if the entity has been dropped. Almost always safe to `.ok()` or `let _ =`.

---

## Async Tasks: Foreground vs Background

| Spawner | Thread | Can call entity.update? | Use for |
|---------|--------|--------------------------|---------|
| `cx.spawn(async move \|cx\| {...})` | Foreground (UI) | Yes | Async I/O, after-await UI updates |
| `cx.background_spawn(async move {...})` | Background pool | No (no `cx`) | CPU-bound work (parsing, hashing) |

### Pattern: foreground spawn for I/O

```rust
impl MyView {
    fn fetch(&mut self, cx: &mut Context<Self>) {
        let weak = cx.entity().downgrade();
        cx.spawn(async move |cx| {
            let result = api_client::fetch().await;
            weak.update(cx, |state, cx| {
                state.data = result.ok();
                cx.notify();
            }).ok();
        })
        .detach();
    }
}
```

### Pattern: background for CPU, then foreground for UI

```rust
impl MyView {
    fn parse_file(&mut self, path: PathBuf, cx: &mut Context<Self>) {
        let weak = cx.entity().downgrade();
        cx.spawn(async move |cx| {
            // Heavy work on background thread
            let parsed = cx.background_executor()
                .spawn(async move { parse_file_sync(&path) })
                .await;

            // Back on foreground — can update entity
            weak.update(cx, |state, cx| {
                state.parsed = Some(parsed);
                cx.notify();
            }).ok();
        })
        .detach();
    }
}
```

---

## Task Lifecycle: Detach vs Hold

```rust
// Detach — task runs to completion or until app exits
cx.spawn(async move |cx| { /* ... */ }).detach();

// Hold — store the Task; dropping the Task cancels it
struct MyView {
    _refresh_task: Option<Task<()>>,
}

impl MyView {
    fn start_refresh(&mut self, cx: &mut Context<Self>) {
        let weak = cx.entity().downgrade();
        let task = cx.spawn(async move |cx| {
            loop {
                cx.background_executor().timer(Duration::from_secs(5)).await;
                let _ = weak.update(cx, |state, cx| {
                    state.refresh();
                    cx.notify();
                });
            }
        });
        self._refresh_task = Some(task);
        // When MyView is dropped, _refresh_task is dropped, the task is cancelled.
    }

    fn stop_refresh(&mut self) {
        self._refresh_task = None;  // explicit cancel
    }
}
```

**Default to holding the `Task`** unless the work must run regardless of view lifetime. Detached tasks that update an entity will silently noop (via `WeakEntity`) but they'll still consume runtime resources.

---

## Subscriptions and Observations

```rust
// Subscribe to events from another entity
struct Parent {
    child: Entity<Child>,
    _subscription: Subscription,
}

impl Parent {
    fn new(cx: &mut Context<Self>) -> Self {
        let child = cx.new(|_| Child::default());
        let subscription = cx.observe(&child, |this, _child, cx| {
            // Called whenever child notifies
            this.recompute(cx);
        });

        Self { child, _subscription: subscription }
    }
}
```

**`Subscription` cleans itself up on drop.** Store it in the struct to control its lifetime — it's released when the parent entity is dropped.

### `cx.observe` vs `cx.subscribe`

| | Triggers when | Use for |
|---|---------------|---------|
| `cx.observe(&entity, ...)` | The observed entity calls `cx.notify()` | Reactive updates |
| `cx.subscribe(&entity, ...)` | The observed entity emits a typed event | Pub/sub messages |

```rust
// Emit a custom event
impl EventEmitter<MyEvent> for MyEntity {}

impl MyEntity {
    fn do_thing(&mut self, cx: &mut Context<Self>) {
        cx.emit(MyEvent::Done);
    }
}

// Subscribe in another entity
let _sub = cx.subscribe(&my_entity, |this, _emitter, event: &MyEvent, cx| {
    match event {
        MyEvent::Done => this.handle_done(cx),
    }
});
```

---

## Actions: Keyboard Shortcuts

```rust
actions!(my_namespace, [SaveFile, OpenFile]);

impl MyView {
    fn register(workspace: &mut Workspace) {
        workspace
            .register_action(|view, _: &SaveFile, window, cx| {
                view.save(window, cx);
            })
            .register_action(|view, _: &OpenFile, window, cx| {
                view.open(window, cx);
            });
    }
}

// Bind in keymap.json:
// "ctrl-s": "my_namespace::SaveFile"
```

### Actions with payloads

```rust
#[derive(Clone, Deserialize, JsonSchema, PartialEq)]
struct SetTheme {
    theme: String,
}

impl_actions!(my_namespace, [SetTheme]);

view.register_action(|view, action: &SetTheme, _window, cx| {
    view.apply_theme(&action.theme, cx);
});
```

---

## Rendering Discipline

### `render` is pure-ish

```rust
impl Render for MyView {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .child(format!("Count: {}", self.count))
            .on_click(cx.listener(|this, _ev, _window, cx| {
                this.count += 1;
                cx.notify();
            }))
    }
}
```

- **Don't spawn tasks in `render`** — it runs on every frame; tasks pile up
- **Don't mutate state in `render`** — use the listener pattern

### `cx.listener` for event handlers

```rust
// ✅ Listener — auto-takes self, no manual weak handling
.on_click(cx.listener(|this, ev, window, cx| {
    this.handle_click(ev, cx);
}))

// ❌ Manual weak — works but unnecessary boilerplate
let weak = cx.entity().downgrade();
.on_click(move |ev, _window, cx| {
    let _ = weak.update(cx, |this, cx| this.handle_click(ev, cx));
})
```

---

## Common Mistakes

```rust
// ❌ Borrowing cx twice
let value = self.entity.read(cx);  // borrows cx
self.entity.update(cx, |...|);     // ERROR: cx already borrowed

// ✅ Drop the read borrow before updating
let value = self.entity.read(cx).field.clone();
self.entity.update(cx, |s, cx| { s.other = value; cx.notify(); });
```

```rust
// ❌ Forgetting cx.notify() — UI doesn't update
self.entity.update(cx, |state, _cx| {
    state.count += 1;
    // state changed but no notify — render not triggered
});

// ✅ Notify when observable state changes
self.entity.update(cx, |state, cx| {
    state.count += 1;
    cx.notify();
});
```

```rust
// ❌ Detached task with strong reference — leaks the entity until task ends
let entity = cx.entity();
cx.spawn(async move |cx| {
    loop {
        cx.background_executor().timer(Duration::from_secs(1)).await;
        entity.update(cx, |state, cx| { state.tick(); cx.notify(); }).ok();
    }
}).detach();
// → entity never drops while loop runs

// ✅ Weak + held Task
let weak = cx.entity().downgrade();
let task = cx.spawn(async move |cx| {
    while let Ok(_) = weak.update(cx, |state, cx| { state.tick(); cx.notify(); }) {
        cx.background_executor().timer(Duration::from_secs(1)).await;
    }
});
self._tick_task = Some(task);
```

---

## Quick Checklist

- [ ] Entities created with `cx.new(|cx| ...)`
- [ ] Closures hold `WeakEntity`, never `Entity`
- [ ] Inside `entity.update`, use the **inner** `cx`, not the outer one
- [ ] `cx.notify()` after every mutation that affects rendering
- [ ] No nested `entity_a.update(cx, |_, cx| entity_b.update(cx, ...))`
- [ ] `cx.background_spawn` (or `cx.background_executor().spawn`) for CPU-bound work
- [ ] `cx.spawn` for I/O + entity updates
- [ ] Tasks held in `Option<Task<()>>` field unless they must outlive the view
- [ ] Subscriptions stored in fields so they drop with the entity
- [ ] `cx.listener` for event handlers in `render`
- [ ] No state mutation or `spawn` calls inside `render`
- [ ] Custom events via `EventEmitter<MyEvent>` + `cx.emit`
- [ ] Actions registered via `register_action`, declared with `actions!` macro
