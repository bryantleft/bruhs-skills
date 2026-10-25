export type NotificationKey = "replies" | "digest" | "product";

export type Settings = {
  name: string;
  email: string;
  workspace: string;
  slug: string;
  notifications: Record<NotificationKey, boolean>;
  apiKey: string;
};

export const INITIAL: Settings = {
  name: "Maya Okafor",
  email: "maya@lanternpress.co",
  workspace: "Lantern Press",
  slug: "lantern-press",
  notifications: { replies: true, digest: true, product: false },
  apiKey: "qk_live_7Hc2pX9vLmQ4rT8wZs1NbE6yUa3dKf0j",
};

export const NOTIFICATIONS: { key: NotificationKey; title: string; description: string }[] = [
  { key: "replies", title: "Comment replies", description: "When someone replies to a comment you left on a doc." },
  { key: "digest", title: "Weekly digest", description: "A Monday summary of what changed in your workspace." },
  { key: "product", title: "Product updates", description: "New features and changes to Quill, about once a month." },
];

/** Workspace URL slug: lowercase ascii words joined by single hyphens. */
export function slugify(input: string): string {
  return input
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** "qk_live_••••••••Kf0j": prefix and last 4 visible. */
export function maskKey(key: string): string {
  const cut = key.lastIndexOf("_") + 1;
  return key.slice(0, cut) + "•".repeat(8) + key.slice(-4);
}

export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}
