import { useState } from "react";
import { INITIAL, NOTIFICATIONS, isValidEmail, maskKey, slugify, type NotificationKey } from "./settings";

function CopyIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="9" y="9" width="13" height="13" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
      <path d="M21 3v5h-5" />
    </svg>
  );
}

function PencilIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

export function App() {
  const [name, setName] = useState(INITIAL.name);
  const [email, setEmail] = useState(INITIAL.email);
  const [workspace, setWorkspace] = useState(INITIAL.workspace);
  const [slug, setSlug] = useState(INITIAL.slug);
  const [notifications, setNotifications] = useState(INITIAL.notifications);
  const [apiKey, setApiKey] = useState(INITIAL.apiKey);
  const [banner, setBanner] = useState(true);
  const [message, setMessage] = useState("");

  const toggle = (key: NotificationKey) =>
    setNotifications((n) => ({ ...n, [key]: !n[key] }));

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidEmail(email)) {
      setMessage("Please enter a valid email");
      return;
    }
    setMessage("Settings saved!");
  };

  const regenerate = () => {
    if (confirm("Regenerate the API key? The old key stops working right away.")) {
      setApiKey("qk_live_" + Math.random().toString(36).slice(2, 14) + "Ab9z");
    }
  };

  const deleteWorkspace = () => {
    confirm(`Delete ${workspace}? This can't be undone.`);
  };

  return (
    <div className="wrapper">
      <div className="topnav">
        <b>Quill</b>
        <span className="crumbs">Lantern Press / Settings</span>
      </div>

      {banner && (
        <div className="banner">
          <span>Your trial ends in 9 days. Add a payment method to keep your workspace.</span>
          <button className="icon-btn" onClick={() => setBanner(false)}>
            <CloseIcon />
          </button>
        </div>
      )}

      <h1>Settings</h1>
      <p className="sub">Manage your account and workspace settings</p>

      <form onSubmit={save}>
        <div className="card">
          <h2>Profile</h2>
          <div className="avatar-row">
            <div className="avatar">MO</div>
            <button type="button" className="icon-btn">
              <PencilIcon />
            </button>
          </div>
          <div className="row">
            <div className="label">Full name</div>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" />
          </div>
          <div className="row">
            <div className="label">Email</div>
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email address" />
          </div>
        </div>

        <div className="card">
          <h2>Workspace</h2>
          <div className="row">
            <div className="label">Workspace name</div>
            <input value={workspace} onChange={(e) => setWorkspace(e.target.value)} placeholder="Workspace name" />
          </div>
          <div className="row">
            <div className="label">Workspace URL</div>
            <div className="slug">
              <span className="prefix">https://quill.so/</span>
              <input
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                onBlur={() => setSlug(slugify(slug))}
                placeholder="your-workspace"
              />
            </div>
          </div>
        </div>

        <div className="card">
          <h2>Notifications</h2>
          {NOTIFICATIONS.map((n) => (
            <div className="notif" key={n.key}>
              <div>
                <div className="notif-title">{n.title}</div>
                <div className="notif-desc">{n.description}</div>
              </div>
              <div className={notifications[n.key] ? "toggle on" : "toggle"} onClick={() => toggle(n.key)}>
                <div className="knob" />
              </div>
            </div>
          ))}
        </div>

        <div className="card">
          <h2>API key</h2>
          <p className="notif-desc">Use this key to call the Quill API from your own scripts.</p>
          <div className="key-row">
            <code>{maskKey(apiKey)}</code>
            <button type="button" className="icon-btn" onClick={() => navigator.clipboard?.writeText(apiKey)}>
              <CopyIcon />
            </button>
            <button type="button" className="icon-btn" onClick={regenerate}>
              <RefreshIcon />
            </button>
          </div>
        </div>

        <div className="actions">
          <button type="submit" className="btn">
            Save
          </button>
          {message && <span className="message">{message}</span>}
        </div>
      </form>

      <div className="card danger">
        <h2>Danger zone</h2>
        <p className="notif-desc">Deleting the workspace removes every doc, comment and member.</p>
        <button type="button" className="btn" onClick={deleteWorkspace}>
          Delete workspace
        </button>
      </div>
    </div>
  );
}
