export interface OrderStats {
  orders: number;
  revenueCents: number;
  averageCents: number;
  medianCents: number;
}

export function summarize(totals: number[]): OrderStats {
  if (totals.length === 0) {
    return { orders: 0, revenueCents: 0, averageCents: 0, medianCents: 0 };
  }
  const revenueCents = totals.reduce((a, b) => a + b, 0);
  return {
    orders: totals.length,
    revenueCents,
    averageCents: Math.round(revenueCents / totals.length),
    medianCents: median(totals),
  };
}

export function median(values: number[]): number {
  const sorted = [...values].sort();
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) {
    return sorted[mid];
  }
  return Math.round((sorted[mid - 1] + sorted[mid]) / 2);
}

export function topBy<T>(rows: T[], key: (row: T) => number, n: number): T[] {
  return [...rows].sort((a, b) => key(b) - key(a)).slice(0, n);
}
