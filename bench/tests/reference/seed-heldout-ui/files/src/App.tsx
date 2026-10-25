import { useId, useState, type FormEvent, type ReactNode } from "react";
import { INITIAL, NOTIFICATIONS, isValidEmail, maskKey, slugify, type NotificationKey } from "./settings";

function Icon({ d, size = 16 }: { d: string[]; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {d.map((path) => (
        <path key={path} d={path} />
      ))}
    </svg>
  );
}

const COPY = ["M8 8h11a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1Z", "M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"];
const REFRESH = ["M21 12a9 9 0 1 1-3-6.7L21 8", "M21 3v5h-5"];
const PENCIL = ["M12 20h9", "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"];
const CLOSE = ["M18 6 6 18", "M6 6l12 12"];

function Field({ label, children, hint }: { label: string; hint?: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <div className="field-control">
        {children(id)}
        {hint && <p className="hint">{hint}</p>}
      </div>
    </div>
  );
}

function Switch({ checked, onChange, labelledBy, describedBy }: {
  checked: boolean; onChange: () => void; labelledBy: string; describedBy: string;
}) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-labelledby={labelledBy}
      aria-describedby={describedBy} className="switch" onClick={onChange}>
      <span className="switch-knob" />
    </button>
  );
}

type Status = { kind: "ok" | "error"; text: string } | null;

export function App() {
  const [name, setName] = useState(INITIAL.name);
  const [email, setEmail] = useState(INITIAL.email);
  const [workspace, setWorkspace] = useState(INITIAL.workspace);
  const [slug, setSlug] = useState(INITIAL.slug);
  const [notifications, setNotifications] = useState(INITIAL.notifications);
  const [apiKey, setApiKey] = useState(INITIAL.apiKey);
  const [banner, setBanner] = useState(true);
  const [status, setStatus] = useState<Status>(null);
  const [copied, setCopied] = useState(false);

  const toggle = (key: NotificationKey) => setNotifications((n) => ({ ...n, [key]: !n[key] }));

  const save = (e: FormEvent) => {
    e.preventDefault();
    if (!isValidEmail(email)) {
      setStatus({ kind: "error", text: "Enter a valid email address." });
      return;
    }
    setStatus({ kind: "ok", text: "Changes saved." });
  };

  const copyKey = async () => {
    await navigator.clipboard?.writeText(apiKey);
    setCopied(true);
  };

  const regenerate = () => {
    if (confirm("Regenerate the API key? The old key stops working right away.")) {
      setApiKey("qk_live_" + Math.random().toString(36).slice(2, 14) + "Ab9z");
      setCopied(false);
    }
  };

  const deleteWorkspace = () => {
    confirm(`Delete ${workspace}? This can't be undone.`);
  };

  return (
    <div className="page">
      <header className="topbar">
        <span className="logo">Quill</span>
        <nav aria-label="Breadcrumb" className="crumbs">
          <span>{workspace}</span>
          <span aria-hidden="true">/</span>
          <span aria-current="page">Settings</span>
        </nav>
      </header>

      {banner && (
        <div className="banner" role="status">
          <p>Your trial ends in 9 days. Add a payment method to keep your workspace.</p>
          <button type="button" className="icon-button" aria-label="Dismiss" onClick={() => setBanner(false)}>
            <Icon d={CLOSE} size={14} />
          </button>
        </div>
      )}

      <main>
        <h1>Settings</h1>
        <p className="lede">Your profile, workspace and notifications.</p>

        <form onSubmit={save} noValidate>
          <section className="card" aria-labelledby="profile-title">
            <h2 id="profile-title">Profile</h2>
            <div className="avatar-row">
              <div className="avatar" aria-hidden="true">MO</div>
              <button type="button" className="button secondary small">
                <Icon d={PENCIL} size={14} />
                Change avatar
              </button>
            </div>
            <Field label="Full name">
              {(id) => <input id={id} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />}
            </Field>
            <Field label="Email">
              {(id) => (
                <input id={id} type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email" aria-invalid={status?.kind === "error" || undefined} />
              )}
            </Field>
          </section>

          <section className="card" aria-labelledby="workspace-title">
            <h2 id="workspace-title">Workspace</h2>
            <Field label="Workspace name">
              {(id) => <input id={id} value={workspace} onChange={(e) => setWorkspace(e.target.value)} />}
            </Field>
            <Field label="Workspace URL" hint="Lowercase letters, numbers and hyphens.">
              {(id) => (
                <div className="affix">
                  <span className="affix-prefix" aria-hidden="true">quill.so/</span>
                  <input id={id} value={slug} onChange={(e) => setSlug(e.target.value)}
                    onBlur={() => setSlug(slugify(slug))} spellCheck={false} />
                </div>
              )}
            </Field>
          </section>

          <section className="card" aria-labelledby="notifications-title">
            <h2 id="notifications-title">Email notifications</h2>
            <ul className="settings-list">
              {NOTIFICATIONS.map((n) => (
                <li key={n.key} className="setting">
                  <div>
                    <p className="setting-title" id={`notif-${n.key}`}>{n.title}</p>
                    <p className="hint" id={`notif-${n.key}-desc`}>{n.description}</p>
                  </div>
                  <Switch checked={notifications[n.key]} onChange={() => toggle(n.key)}
                    labelledBy={`notif-${n.key}`} describedBy={`notif-${n.key}-desc`} />
                </li>
              ))}
            </ul>
          </section>

          <section className="card" aria-labelledby="api-title">
            <h2 id="api-title">API key</h2>
            <p className="hint">Use this key to call the Quill API from your own scripts.</p>
            <div className="key-row">
              <code className="key">{maskKey(apiKey)}</code>
              <div className="key-actions">
                <button type="button" className="button secondary small" onClick={copyKey}>
                  <Icon d={COPY} size={14} />
                  {copied ? "Copied" : "Copy"}
                </button>
                <button type="button" className="button secondary small" onClick={regenerate}>
                  <Icon d={REFRESH} size={14} />
                  Regenerate
                </button>
              </div>
            </div>
          </section>

          <div className="form-actions">
            <p className={`status ${status?.kind ?? ""}`} role="status">
              {status?.text}
            </p>
            <button type="submit" className="button primary">
              Save changes
            </button>
          </div>
        </form>

        <section className="card danger" aria-labelledby="danger-title">
          <div>
            <h2 id="danger-title">Delete workspace</h2>
            <p className="hint">Removes every doc, comment and member. This can't be undone.</p>
          </div>
          <button type="button" className="button destructive" onClick={deleteWorkspace}>
            Delete workspace
          </button>
        </section>
      </main>
    </div>
  );
}
