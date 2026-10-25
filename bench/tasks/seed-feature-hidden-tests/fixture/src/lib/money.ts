const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

/** 123456 -> "$1,234.56", -300 -> "-$3.00" */
export function formatCents(cents: number): string {
  return usd.format(cents / 100);
}

/**
 * Split `totalCents` into `parts` integer shares that add up exactly. The first
 * `totalCents % parts` shares get the leftover cent: splitCents(1000, 3) -> [334, 333, 333].
 */
export function splitCents(totalCents: number, parts: number): number[] {
  if (!Number.isInteger(totalCents) || totalCents < 0) {
    throw new RangeError(`amount must be a non-negative whole number of cents, got ${totalCents}`);
  }
  if (!Number.isInteger(parts) || parts < 1) {
    throw new RangeError(`can't split between ${parts} people`);
  }
  const base = Math.floor(totalCents / parts);
  const extra = totalCents % parts;
  return Array.from({ length: parts }, (_, i) => base + (i < extra ? 1 : 0));
}
