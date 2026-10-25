const formatters = new Map<string, Intl.NumberFormat>();

export function formatCents(cents: number, currency = "USD"): string {
  let fmt = formatters.get(currency);
  if (!fmt) {
    fmt = new Intl.NumberFormat("en-US", { style: "currency", currency });
    formatters.set(currency, fmt);
  }
  return fmt.format(cents / 100);
}

export function lineTotal(unitPriceCents: number, quantity: number): number {
  return unitPriceCents * quantity;
}

export function orderTotal(items: { unitPriceCents: number; quantity: number }[]): number {
  return items.reduce((sum, item) => sum + lineTotal(item.unitPriceCents, item.quantity), 0);
}

export function parsePriceCents(text: string): number {
  const trimmed = text.trim().replace(/^\$/, "");
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) {
    throw new Error(`invalid price: ${text}`);
  }
  const [whole, frac = ""] = trimmed.split(".");
  return Number(whole) * 100 + Number(frac.padEnd(2, "0"));
}
