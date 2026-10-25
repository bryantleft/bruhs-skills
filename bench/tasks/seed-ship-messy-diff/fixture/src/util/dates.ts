const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;

export function parseDay(text: string): Date {
  if (!DAY_RE.test(text)) {
    throw new Error(`expected a date like 2026-10-01, got "${text}"`);
  }
  const date = new Date(`${text}T00:00:00Z`);
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== text) {
    throw new Error(`not a real date: ${text}`);
  }
  return date;
}

export function dayKey(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function endOfDay(date: Date): Date {
  return new Date(date.getTime() + 24 * 60 * 60 * 1000 - 1);
}

export function hoursBetween(start: Date, end: Date): number {
  return (end.getTime() - start.getTime()) / (60 * 60 * 1000);
}

export function formatHours(hours: number): string {
  return hours.toFixed(2);
}
