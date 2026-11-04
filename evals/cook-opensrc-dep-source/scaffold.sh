#!/usr/bin/env bash
# Next.js car-rental app whose rental form still uses two <input type="date">.
# react-day-picker 9.4.4 is locked in package-lock.json and installed in
# node_modules/ (a trimmed copy: package.json, types, the range logic and the
# stylesheet). The business rule is "at most 7 calendar days, pick-up and
# return day both counted" (src/lib/rental-range.ts), but in this version a
# range picker's `max` counts nights (differenceInCalendarDays in
# dist/index.js), so the right prop is max={6}; the stylesheet is exported as
# "react-day-picker/style.css" only. A run that reads the installed source gets
# both right; one that codes from memory of the name or of v8 doesn't.
# opensrc is not installed and could not fetch offline anyway.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project rental-app next react react-dom react-day-picker tailwindcss
node -e '
const fs = require("fs");
const p = JSON.parse(fs.readFileSync("package.json"));
p.scripts = { dev: "next dev", ...p.scripts };
p.dependencies = { next: "^15.3.0", react: "^19.1.0", "react-dom": "^19.1.0", "react-day-picker": "^9.4.0", tailwindcss: "^4.1.0" };
fs.writeFileSync("package.json", JSON.stringify(p, null, 2) + "\n");
'
eval_state <<'JSON'
{
  "stack": {"structure": "single", "language": "typescript", "framework": "Next.js", "styling": ["Tailwind CSS"], "libraries": ["react-day-picker"], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write package-lock.json <<'EOF'
{
  "name": "rental-app",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "rental-app",
      "dependencies": {
        "next": "^15.3.0",
        "react": "^19.1.0",
        "react-day-picker": "^9.4.0",
        "react-dom": "^19.1.0",
        "tailwindcss": "^4.1.0"
      }
    },
    "node_modules/react-day-picker": {
      "version": "9.4.4",
      "resolved": "https://registry.npmjs.org/react-day-picker/-/react-day-picker-9.4.4.tgz",
      "license": "MIT",
      "dependencies": {
        "@date-fns/tz": "^1.2.0",
        "date-fns": "^4.1.0"
      },
      "peerDependencies": {
        "react": ">=16.8.0"
      }
    }
  }
}
EOF

eval_write src/lib/rental-range.ts <<'EOF'
// Pricing policy (finance, 2026-02): a rental covers at most 7 calendar days,
// counting both the pick-up day and the return day.
export const MAX_RENTAL_DAYS = 7;

export type RentalRange = { readonly pickUp: Date; readonly returnOn: Date };

const DAY_MS = 24 * 60 * 60 * 1000;

function startOfDayUtc(d: Date): number {
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
}

/** Calendar days covered, both ends included: same-day rental = 1. */
export function rentalDays(range: RentalRange): number {
  return Math.round((startOfDayUtc(range.returnOn) - startOfDayUtc(range.pickUp)) / DAY_MS) + 1;
}

export type RangeCheck =
  | { readonly ok: true }
  | { readonly ok: false; readonly reason: "return_before_pick_up" | "too_long"; readonly days: number };

export function checkRentalRange(range: RentalRange): RangeCheck {
  const days = rentalDays(range);
  if (days < 1) return { ok: false, reason: "return_before_pick_up", days };
  if (days > MAX_RENTAL_DAYS) return { ok: false, reason: "too_long", days };
  return { ok: true };
}
EOF

eval_write src/lib/rental-range.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { checkRentalRange, rentalDays } from "./rental-range.ts";

const d = (s: string) => new Date(`${s}T00:00:00Z`);

test("a same-day rental is one day", () => {
  assert.equal(rentalDays({ pickUp: d("2026-07-01"), returnOn: d("2026-07-01") }), 1);
});

test("Monday to Sunday is the 7-day maximum", () => {
  assert.deepEqual(checkRentalRange({ pickUp: d("2026-07-06"), returnOn: d("2026-07-12") }), { ok: true });
});

test("an 8th day is too long", () => {
  const result = checkRentalRange({ pickUp: d("2026-07-06"), returnOn: d("2026-07-13") });
  assert.deepEqual(result, { ok: false, reason: "too_long", days: 8 });
});
EOF

eval_write src/app/rent/rental-form.tsx <<'EOF'
"use client";

import { useState } from "react";
import { checkRentalRange } from "../../lib/rental-range";

export function RentalForm({ onSubmit }: { onSubmit: (pickUp: Date, returnOn: Date) => void }) {
  const [pickUp, setPickUp] = useState("");
  const [returnOn, setReturnOn] = useState("");
  const check = pickUp && returnOn ? checkRentalRange({ pickUp: new Date(pickUp), returnOn: new Date(returnOn) }) : undefined;
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (check?.ok) onSubmit(new Date(pickUp), new Date(returnOn));
      }}
    >
      <label className="block">
        Pick-up <input type="date" value={pickUp} onChange={(e) => setPickUp(e.target.value)} />
      </label>
      <label className="block">
        Return <input type="date" value={returnOn} onChange={(e) => setReturnOn(e.target.value)} />
      </label>
      {check && !check.ok && <p role="alert">That range is {check.days} days; the most is 7.</p>}
      <button type="submit" disabled={!check?.ok}>Continue</button>
    </form>
  );
}
EOF

eval_write src/app/rent/page.tsx <<'EOF'
import { RentalForm } from "./rental-form";

export default function RentPage() {
  return (
    <main className="mx-auto max-w-md p-6">
      <h1 className="mb-4 text-xl font-semibold">Rent a car</h1>
      <RentalForm onSubmit={() => {}} />
    </main>
  );
}
EOF

eval_commit "feat: rental form with date inputs"

# The installed dependency. node_modules/ is gitignored, as in any real checkout.
P=node_modules/react-day-picker
eval_write $P/package.json <<'EOF'
{
  "name": "react-day-picker",
  "version": "9.4.4",
  "description": "Customizable Date Picker for React",
  "license": "MIT",
  "type": "module",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js"
    },
    "./style.css": "./dist/style.css",
    "./package.json": "./package.json"
  },
  "sideEffects": ["*.css"],
  "dependencies": {
    "@date-fns/tz": "^1.2.0",
    "date-fns": "^4.1.0"
  },
  "peerDependencies": {
    "react": ">=16.8.0"
  }
}
EOF

eval_write $P/dist/index.d.ts <<'EOF'
import type { JSX, KeyboardEvent, MouseEvent } from "react";

/** A range of days. `to` is unset while the user has picked only the start. */
export type DateRange = { from: Date | undefined; to?: Date | undefined };

export type DateBefore = { before: Date };
export type DateAfter = { after: Date };
export type DateInterval = { before: Date; after: Date };
export type DayOfWeek = { dayOfWeek: number | number[] };
export type Matcher = boolean | ((date: Date) => boolean) | Date | Date[] | DateRange | DateBefore | DateAfter | DateInterval | DayOfWeek;

export type Modifiers = Record<string, boolean>;

/** Names of the elements DayPicker renders; keys of `classNames`. */
export type UI =
  | "root" | "months" | "month" | "month_caption" | "caption_label" | "nav" | "button_previous" | "button_next"
  | "month_grid" | "weekdays" | "weekday" | "weeks" | "week" | "day" | "day_button" | "chevron";
/** Selection and day states; also keys of `classNames`. */
export type SelectionState = "selected" | "range_start" | "range_middle" | "range_end";
export type DayFlag = "disabled" | "hidden" | "outside" | "focused" | "today";
export type ClassNames = Record<UI | SelectionState | DayFlag, string>;

export type CustomComponents = {
  /** Replaces the v8 `IconLeft` / `IconRight` components. */
  Chevron: (props: { orientation?: "left" | "right" | "up" | "down"; className?: string }) => JSX.Element;
  DayButton: (props: JSX.IntrinsicElements["button"] & { day: { date: Date }; modifiers: Modifiers }) => JSX.Element;
};

export interface PropsBase {
  numberOfMonths?: number;
  /** The month shown first. Defaults to the selected month or today. */
  defaultMonth?: Date;
  /** The earliest month the user can navigate to. */
  startMonth?: Date;
  /** The latest month the user can navigate to. */
  endMonth?: Date;
  disabled?: Matcher | Matcher[];
  hidden?: Matcher | Matcher[];
  showOutsideDays?: boolean;
  classNames?: Partial<ClassNames>;
  components?: Partial<CustomComponents>;
  className?: string;
}

export interface PropsRange {
  mode: "range";
  /** When true, a selected range can't be cleared by clicking it again. */
  required?: boolean;
  selected?: DateRange | undefined;
  /**
   * Called with the new range (undefined once cleared), the day that was
   * clicked, its modifiers, and the event.
   */
  onSelect?: (selected: DateRange | undefined, triggerDate: Date, modifiers: Modifiers, e: MouseEvent | KeyboardEvent) => void;
  /** Minimum number of nights in the range (see `addToRange`). */
  min?: number;
  /**
   * Maximum number of nights in the range (see `addToRange`). Nights, not
   * days: a range from the 1st to the 3rd is 2 nights.
   */
  max?: number;
  /** Don't let a range span disabled days. */
  excludeDisabled?: boolean;
}

export type DayPickerProps = PropsBase & PropsRange;

export declare function DayPicker(props: DayPickerProps): JSX.Element;

/**
 * Applies a click on `date` to `range`. Returns the new range, or a range
 * that restarts at `date` when the result would be shorter than `min` or
 * longer than `max` nights.
 */
export declare function addToRange(date: Date, range: DateRange | undefined, min?: number, max?: number, required?: boolean): DateRange | undefined;
EOF

eval_write $P/dist/index.js <<'EOF'
import { createElement } from "react";
import { differenceInCalendarDays, isSameDay } from "date-fns";

/**
 * Applies a click on `date` to `range`. `min` and `max` are numbers of
 * nights: differenceInCalendarDays(to, from). 0 means no limit.
 */
export function addToRange(date, range, min = 0, max = 0, required = false) {
  const { from, to } = range || {};
  let next;
  if (!from) {
    next = { from: date, to: min > 0 ? undefined : date };
  } else if (from && to && isSameDay(from, date) && isSameDay(to, date)) {
    next = required ? { from, to } : undefined;
  } else if (from && date < from) {
    next = { from: date, to };
  } else if (from && to && isSameDay(to, date)) {
    next = { from, to: required ? to : undefined };
  } else {
    next = { from, to: date };
  }
  if (next && next.from && next.to) {
    const nights = differenceInCalendarDays(next.to, next.from);
    if ((max > 0 && nights > max) || (min > 0 && nights < min)) {
      next = { from: date, to: undefined };
    }
  }
  return next;
}

export function DayPicker(props) {
  const { mode, selected, onSelect, min, max, required } = props;
  if (mode !== "range") throw new Error(`react-day-picker: this build supports mode="range" only, got ${mode}`);
  const select = (date, modifiers, e) => onSelect?.(addToRange(date, selected, min, max, required), date, modifiers, e);
  return createElement("div", { className: "rdp-root", "data-mode": mode, onSelectDay: select });
}
EOF

eval_write $P/dist/style.css <<'EOF'
.rdp-root { --rdp-accent-color: blue; --rdp-day-height: 44px; --rdp-day-width: 44px; }
.rdp-range_start .rdp-day_button, .rdp-range_end .rdp-day_button { background: var(--rdp-accent-color); color: white; }
.rdp-range_middle { background: color-mix(in srgb, var(--rdp-accent-color) 15%, transparent); }
.rdp-disabled { opacity: 0.4; }
EOF

eval_write $P/README.md <<'EOF'
# React DayPicker

Customizable date picker component for React. Docs: https://daypicker.dev

```bash
npm install react-day-picker
```
EOF

eval_origin
eval_gh
