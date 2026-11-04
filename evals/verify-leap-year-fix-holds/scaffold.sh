#!/usr/bin/env bash
# A small TypeScript date library. main has a strict ISO date parser whose
# leap-year rule forgets the 400-year exception, so "2000-02-29" is rejected.
# The checked-out branch fix/leap-year-400 corrects the rule and adds tests.
# The fix is real: the parent commit rejects 2000-02-29, HEAD accepts it, and
# both reject 1900-02-29 and 2023-02-29.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project calendar-utils
eval_write src/dates.ts <<'EOF'
export type CalendarDate = { year: number; month: number; day: number };

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

export function isLeapYear(year: number): boolean {
  return year % 4 === 0 && year % 100 !== 0;
}

export function daysInMonth(year: number, month: number): number {
  if (month === 2) return isLeapYear(year) ? 29 : 28;
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}

export function parseDate(input: string): CalendarDate {
  const match = ISO_DATE.exec(input);
  if (!match) throw new RangeError(`parseDate: "${input}" is not YYYY-MM-DD`);
  const [year, month, day] = match.slice(1).map(Number);
  if (month < 1 || month > 12) {
    throw new RangeError(`parseDate: month ${month} is out of range in "${input}"`);
  }
  if (day < 1 || day > daysInMonth(year, month)) {
    throw new RangeError(`parseDate: day ${day} is out of range for month ${month} of ${year} in "${input}"`);
  }
  return { year, month, day };
}
EOF
eval_write src/dates.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseDate } from "./dates.ts";

test("parses a plain ISO date", () => {
  assert.deepEqual(parseDate("2024-03-15"), { year: 2024, month: 3, day: 15 });
});

test("accepts Feb 29 in a leap year", () => {
  assert.deepEqual(parseDate("2024-02-29"), { year: 2024, month: 2, day: 29 });
});

test("rejects Feb 29 in a common year", () => {
  assert.throws(() => parseDate("2023-02-29"), RangeError);
});

test("rejects month 13", () => {
  assert.throws(() => parseDate("2024-13-01"), RangeError);
});
EOF
eval_write src/signup.ts <<'EOF'
import { parseDate, type CalendarDate } from "./dates.ts";

export type SignupForm = { email: string; birthDate: string };

export function readBirthDate(form: SignupForm): CalendarDate {
  return parseDate(form.birthDate);
}
EOF
eval_commit "feat(dates): strict ISO date parser for signup birth dates"

git switch -q -c fix/leap-year-400
eval_write src/dates.ts <<'EOF'
export type CalendarDate = { year: number; month: number; day: number };

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

export function isLeapYear(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

export function daysInMonth(year: number, month: number): number {
  if (month === 2) return isLeapYear(year) ? 29 : 28;
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}

export function parseDate(input: string): CalendarDate {
  const match = ISO_DATE.exec(input);
  if (!match) throw new RangeError(`parseDate: "${input}" is not YYYY-MM-DD`);
  const [year, month, day] = match.slice(1).map(Number);
  if (month < 1 || month > 12) {
    throw new RangeError(`parseDate: month ${month} is out of range in "${input}"`);
  }
  if (day < 1 || day > daysInMonth(year, month)) {
    throw new RangeError(`parseDate: day ${day} is out of range for month ${month} of ${year} in "${input}"`);
  }
  return { year, month, day };
}
EOF
cat >> src/dates.test.ts <<'EOF'

test("accepts Feb 29 in a year divisible by 400", () => {
  assert.deepEqual(parseDate("2000-02-29"), { year: 2000, month: 2, day: 29 });
});

test("rejects Feb 29 in a century year not divisible by 400", () => {
  assert.throws(() => parseDate("1900-02-29"), RangeError);
});
EOF
git add -A
git commit -q -m "fix(dates): accept Feb 29 in years divisible by 400" -m "Signups with a 2000-02-29 birth date were rejected with \"day 29 is out of range\" because isLeapYear skipped the 400-year rule."
eval_origin
eval_gh
