# Leptos Patterns

Best practices for Leptos 0.8.x. Loaded by `cook` and `slop` when `leptos` is in `Cargo.toml`.

> Leptos is a fine-grained reactive framework: signals are the primitives, components are functions that wire them up, the `view!` macro produces real DOM nodes that update only the leaf they depend on. Reactivity is *automatic* — your job is to make it cheap.

---

## Reactive Primitives

### Signals — start here

```rust
// ✅ Tuple form — most common
let (count, set_count) = signal(0);

// ✅ RwSignal — when you want one handle that reads and writes
let count = RwSignal::new(0);

// Read
count.get()         // clones value (use for Copy types like u64, bool)
count.read()        // returns a guard — use for non-Copy types
count.with(|v| v.len())  // borrow inside a closure

// Write
set_count.set(42);
set_count.update(|n| *n += 1);
count.write();      // RwSignal: returns a write guard
```

### `get` vs `read` vs `with`

| | Returns | Use when |
|---|---------|----------|
| `.get()` | Owned `T` (clones) | `T: Copy` or you want a snapshot |
| `.read()` | Read guard | Non-`Copy` `T`, need short borrow |
| `.with(\|v\| ...)` | Closure result | Compute on borrowed value, no clone |
| `.get_untracked()` | Owned `T`, no subscription | Read inside `Effect` without re-running |

```rust
// ❌ Cloning a Vec on every render
let items = items.get();
view! { <p>{items.len()}</p> }

// ✅ Borrow with .with — no clone
let count = items.with(|v| v.len());
view! { <p>{count}</p> }
```

### Memo for derived values

```rust
let count = RwSignal::new(0);
let doubled = Memo::new(move |_| count.get() * 2);

// Memos cache: doubled only recomputes when count changes
// AND only re-notifies subscribers when its value actually differs
```

### Effect for side effects only

```rust
// ✅ Effect — runs after reactive deps change, side effects (logging, DOM, async)
Effect::new(move |_| {
    log::info!("count is now {}", count.get());
});

// ❌ Don't use Effect to derive a value — use Memo instead
let doubled = RwSignal::new(0);
Effect::new(move |_| doubled.set(count.get() * 2));  // wrong

// ✅ Use Memo
let doubled = Memo::new(move |_| count.get() * 2);
```

---

## Components

```rust
#[component]
pub fn Card(
    title: String,
    #[prop(optional)] subtitle: Option<String>,
    #[prop(default = false)] dismissible: bool,
    #[prop(into)] on_close: Callback<()>,
    children: Children,
) -> impl IntoView {
    view! {
        <div class="card">
            <h2>{title}</h2>
            {subtitle.map(|s| view! { <p class="subtitle">{s}</p> })}
            {children()}
            {dismissible.then(|| view! {
                <button on:click=move |_| on_close.run(())>"×"</button>
            })}
        </div>
    }
}
```

### Prop attributes

| Attribute | Use |
|-----------|-----|
| `#[prop(optional)]` | Becomes `Option<T>`, defaults to `None` |
| `#[prop(default = expr)]` | Provide a default value |
| `#[prop(into)]` | Auto-call `.into()` on the prop |
| `#[prop(name = "type")]` | Rename for HTML attribute conflicts |

### `Children` vs `ChildrenFn`

```rust
// Children — render once
fn Card(children: Children) -> impl IntoView { view! { <div>{children()}</div> } }

// ChildrenFn — render multiple times (used by <For>, <Show>, etc.)
fn Repeat(times: usize, children: ChildrenFn) -> impl IntoView {
    (0..times).map(move |_| children()).collect_view()
}
```

---

## Async Data: `Resource`

```rust
let user_id = RwSignal::new(1u64);

let user = Resource::new(
    move || user_id.get(),                                  // source signal
    |id| async move { fetch_user(id).await }                // async fetcher
);

view! {
    <Suspense fallback=|| view! { <p>"Loading..."</p> }>
        {move || user.get().map(|u| match u {
            Ok(user) => view! { <UserCard user/> }.into_any(),
            Err(e) => view! { <p>"Error: " {e.to_string()}</p> }.into_any(),
        })}
    </Suspense>
}
```

### `Suspense` vs `Transition`

| Component | Behavior on re-fetch |
|-----------|----------------------|
| `<Suspense>` | Shows fallback every time the resource refetches |
| `<Transition>` | Keeps showing old data until new data arrives, no flash |

Use `<Transition>` for filter/search UIs where flashing the loader would be jarring.

---

## Action: Side-Effecting Calls

```rust
let save = Action::new(|input: &SaveInput| {
    let input = input.clone();  // Action stores the input
    async move { save_to_server(input).await }
});

view! {
    <form on:submit=move |ev| {
        ev.prevent_default();
        save.dispatch(SaveInput { /* ... */ });
    }>
        <input name="title"/>
        <button disabled=move || save.pending().get()>
            {move || if save.pending().get() { "Saving..." } else { "Save" }}
        </button>
        {move || save.value().get().map(|result| match result {
            Ok(()) => view! { <p class="ok">"Saved"</p> }.into_any(),
            Err(e) => view! { <p class="err">{e.to_string()}</p> }.into_any(),
        })}
    </form>
}
```

---

## Conditional & List Rendering

### `<Show>` over `move || if`

```rust
// ✅ <Show> only re-runs when the predicate changes truthiness
<Show
    when=move || count.get() > 0
    fallback=|| view! { <p>"Empty"</p> }
>
    <p>"Has items"</p>
</Show>

// ⚠️ This re-renders the whole subtree on every count change
{move || if count.get() > 0 {
    view! { <p>"Has items"</p> }.into_any()
} else {
    view! { <p>"Empty"</p> }.into_any()
}}
```

### `<For>` for keyed lists

```rust
<For
    each=move || items.get()
    key=|item| item.id          // stable key — Leptos diffs by this
    children=move |item| view! {
        <li>{item.name}</li>
    }
/>
```

The `key` is critical. Without it (or with `|item| item.clone()`), every re-render rebuilds every row.

---

## Ownership: The Leptos Trap

Signals are `Copy` (they're really stored elsewhere — the signal itself is a handle). But many other values aren't, and closures capture by move by default.

### `Copy` types — pass freely

`Signal<T>`, `RwSignal<T>`, `Memo<T>`, `ReadSignal<T>`, `WriteSignal<T>`, `Callback<T>` — all `Copy`. Just pass them.

### Non-`Copy` values — `StoredValue`

```rust
// ❌ Can't move `client` into multiple closures
let client = ApiClient::new();
let on_load = move || { client.load(); };
let on_save = move || { client.save(); };  // ERROR: client moved above

// ✅ StoredValue — Copy handle to a shared value
let client = StoredValue::new(ApiClient::new());

let on_load = move || { client.with_value(|c| c.load()); };
let on_save = move || { client.with_value(|c| c.save()); };
```

### `StoredValue::get_value` inside async

```rust
let api = StoredValue::new(api_client);

// ❌ Get value outside — captures by move once
let api_value = api.get_value();
Effect::new(move |_| {
    spawn_local(async move { api_value.fetch().await; });  // moved on first run
});

// ✅ Get value inside the Effect — fresh each run
Effect::new(move |_| {
    let api = api.get_value();
    spawn_local(async move { api.fetch().await; });
});
```

### `Callback` for parent → child events

```rust
#[component]
fn DeleteButton(on_delete: Callback<u64>) -> impl IntoView {
    view! { <button on:click=move |_| on_delete.run(item_id)>"Delete"</button> }
}

// Parent:
let on_delete = Callback::new(move |id: u64| {
    set_items.update(|items| items.retain(|i| i.id != id));
});
view! { <DeleteButton on_delete/> }
```

---

## Effect Loops (Common Trap)

```rust
// ❌ Infinite loop — Effect reads `count`, then writes to `count`,
// which re-triggers the Effect
Effect::new(move |_| {
    set_count.set(count.get() + 1);
});

// ✅ Read with get_untracked — no subscription
Effect::new(move |_| {
    if should_increment.get() {
        let current = count.get_untracked();
        set_count.set(current + 1);
    }
});
```

---

## Context for App-Wide State

```rust
#[derive(Clone)]
struct AppState {
    user: RwSignal<Option<User>>,
    theme: RwSignal<Theme>,
}

#[component]
pub fn App() -> impl IntoView {
    provide_context(AppState {
        user: RwSignal::new(None),
        theme: RwSignal::new(Theme::Dark),
    });

    view! { <Router>...</Router> }
}

// Anywhere downstream:
let state = expect_context::<AppState>();
let user = state.user;
```

`AppState` is `Clone` because it only contains `Copy` signals — cloning is cheap. **Don't put non-`Copy` data in context** unless wrapped in `StoredValue` or `Arc`.

---

## CSR vs SSR Differences

This project uses **CSR-only** (`features = ["csr"]`). Notes on shared patterns:

### `spawn_local` for async in event handlers

```rust
// ✅ CSR — spawn_local runs the future on the main thread
on:click=move |_| {
    spawn_local(async move {
        let result = api.save().await;
        // update signals after await
    });
}
```

### `Effect` runs only in the browser

In SSR, `Effect::new` does nothing on the server (since side effects shouldn't run during render). In CSR-only, it runs as expected.

---

## `view!` Macro Discipline

### Use `class:` for conditional classes

```rust
// ✅ class:foo=cond — toggles "foo" based on cond
view! {
    <button
        class="btn"
        class:active=move || is_active.get()
        class:disabled=move || is_disabled.get()
    >
        "Click"
    </button>
}
```

### Use `style:` for inline styles

```rust
view! {
    <div
        style:width=move || format!("{}px", width.get())
        style:background-color=move || color.get()
    />
}
```

### `prop:` for properties (vs attributes)

```rust
// ✅ prop:value — sets the JS property (textarea, input, etc.)
view! { <input type="text" prop:value=move || text.get()/> }
```

### Event handlers with `on:`

```rust
view! {
    <button on:click=move |_ev: web_sys::MouseEvent| { /* ... */ }/>
    <input on:input=move |ev| {
        let value = event_target_value(&ev);
        set_text.set(value);
    }/>
}
```

---

## Performance

### Avoid re-rendering the world

```rust
// ❌ This runs on EVERY count change, even though we only use the length
view! {
    <p>{move || format!("Items: {}", items.get().len())}</p>
}

// ✅ Memo caches the length — only re-renders if length changes
let count = Memo::new(move |_| items.with(|v| v.len()));
view! {
    <p>"Items: " {count}</p>
}
```

### Don't clone signals in closures

```rust
// ❌ Pointless clone — signals are Copy
let count_clone = count.clone();
move || count_clone.get()

// ✅ Just use it
move || count.get()
```

---

## Quick Checklist

- [ ] Signals (`signal`, `RwSignal`) for state, `Memo` for derived, `Effect` for side effects
- [ ] `.with(|v| ...)` to borrow non-`Copy` signal values, not `.get()`
- [ ] `Resource` for async data, `<Suspense>` or `<Transition>` to render
- [ ] `Action` for fire-and-handle (form submit, mutations)
- [ ] `<Show>` over `move || if`
- [ ] `<For>` always with a stable `key`
- [ ] `StoredValue` for non-`Copy` values shared across closures
- [ ] `get_value()` inside `Effect`, not outside
- [ ] `Callback<T>` for parent→child event handlers
- [ ] `get_untracked()` to break Effect loops
- [ ] Context only holds `Copy` (or `Arc`-wrapped) state
- [ ] No `.clone()` on signals — they're `Copy`
- [ ] `class:`, `style:`, `prop:`, `on:` directives for dynamic attributes
