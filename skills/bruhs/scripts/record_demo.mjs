#!/usr/bin/env node
// record_demo.mjs — record a browser demo the way a person would show it.
//
// The agent writes a shot list (JSON: a URL, a device and a few steps). This
// script drives Chromium through it with Playwright and renders an MP4 that:
//
//   - is captured at device pixels (viewport × scale), not CSS pixels, so text
//     stays sharp and zoomed-in detail is real detail, not upscaled blur;
//   - shows a cursor that moves like a hand (curved, eased, Fitts-timed),
//     changes to a hand over links and an I-beam over text, and presses on
//     click; on touch devices it shows touch indicators for taps, swipes and
//     scrolls instead;
//   - zooms the camera in on the element each action touches, pans between
//     nearby actions, and zooms back out before scrolls and navigations;
//   - shows keyboard shortcuts as on-screen key chips.
//
// Everything runs locally. Steps are deterministic Playwright locators, so
// the same shot list re-records the same video after a fix.
//
// Usage:
//   node record_demo.mjs check   SHOTS.json
//   node record_demo.mjs observe URL|SHOTS.json [--device NAME] [--steps]
//   node record_demo.mjs record  SHOTS.json --out DIR [--headed] [--keep-work]
//
// Exit codes: 0 ok, 2 usage or shot-list validation error, 3 a required tool
// is missing (playwright, chromium, ffmpeg), 4 a step or the render failed.

import { spawn, spawnSync, execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { performance } from 'node:perf_hooks';

const EXIT_OK = 0;
const EXIT_INVALID = 2;
const EXIT_MISSING_TOOL = 3;
const EXIT_FAILED = 4;

class DemoError extends Error {
  constructor(message, code) { super(message); this.code = code; }
}

// ── Defaults (each has a reason) ──────────────────────────────────────────
// Desktop: a 1280×720 CSS viewport is what most laptops show a web app at and
// is 16:9, so it fills a 1920×1080 frame with no bars. Scale 2 captures
// 2560×1440 device pixels: 1.33 source pixels per output pixel at zoom 1, and
// still ≥ 0.8 at the default 1.6 max auto-zoom (RESOLUTION_FLOOR below).
// Scale 3 would allow deeper zooms, but under continuous animation the
// screencast measured 25 fps at scale 3 against 51 at scale 2 (60 at scale 1).
const DESKTOP = { viewport: { width: 1280, height: 720 }, scale: 2, output: [1920, 1080], maxZoom: 1.6 };
// Mobile: Playwright's iPhone 15 descriptor (393×659, DPR 3, touch) captured
// at 1179×1977, framed in a 1080×1920 portrait video.
const MOBILE_DEVICE = 'iPhone 15';
const MOBILE = { output: [1080, 1920], maxZoom: 1.5 };
const FPS = 60;                 // cursor and camera motion are synthesized, so 60 is free smoothness
const JPEG_QUALITY = 90;        // screencast frames; q90 keeps text edges clean at ~1/5 the size of PNG
// Source pixels per output pixel below which zoomed detail visibly softens.
// 0.8 = at most a 25% upscale, the point where 1px text strokes start to blur.
const RESOLUTION_FLOOR = 0.8;
const TARGET_MAX_SECONDS = 60;  // a demo clip longer than this loses reviewers; warn, don't fail

// Motion timing. Cursor travel follows Fitts' law, T = a + b·log2(D/W + 1),
// with a and b in the range measured for mouse pointing (a ≈ 0.2–0.3 s,
// b ≈ 0.1–0.15 s/bit), clamped so long moves don't drag.
const FITTS_A = 0.25, FITTS_B = 0.12, MOVE_MIN_S = 0.32, MOVE_MAX_S = 1.1;
const DWELL_BEFORE_CLICK_MS = 140; // people settle on a target before pressing
const CLICK_HOLD_MS = 70;          // mouse button down time
const STEP_PAUSE_MS = 450;         // default beat after each step so the result is seen
const TYPE_DELAY_MS = 55, TYPE_JITTER_MS = 30;
const SCROLL_SPEED = 900;          // px/s for scroll gestures, a brisk but readable scroll

// Camera.
const ZOOM_IN_S = 0.85, ZOOM_OUT_S = 1.0, PAN_S = 0.7;
const GROUP_GAP_S = 1.6;   // actions closer than this share one zoomed shot
const LINGER_S = 0.8;      // stay zoomed this long after the last action of a shot
const MIN_ZOOM = 1.15;     // a smaller zoom reads as jitter, not emphasis
const FIT_PAD = 0.4;       // auto-zoom leaves 40% of the viewport around the target
const EXPLICIT_HOLD_MS = 2000;

const ACTIONS = ['goto', 'click', 'tap', 'type', 'press', 'hover', 'scroll', 'swipe', 'drag', 'select',
  'wait', 'waitFor', 'zoom', 'mark'];
const COMMON_KEYS = ['pause', 'camera', 'timeout', 'note'];
const ACTION_KEYS = {
  goto: [], click: [], tap: [], hover: [], mark: [], wait: [], waitFor: [],
  type: ['text', 'delay', 'clear'],
  press: [],
  scroll: ['by', 'within'],
  swipe: ['direction', 'distance'],
  drag: ['to'],
  select: ['value'],
  zoom: ['scale', 'hold'],
};
const TARGET_KINDS = ['role', 'text', 'label', 'placeholder', 'testId', 'css', 'alt', 'title'];
const TOP_KEYS = ['url', 'device', 'viewport', 'scale', 'colorScheme', 'storageState', 'output', 'zoom',
  'cursor', 'redact', 'scrollbars', 'setup', 'steps', 'seed', 'title', 'note'];

// ── Small helpers ─────────────────────────────────────────────────────────

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const nonEmpty = (v) => typeof v === 'string' && v.trim() !== '';

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function stepAction(step) {
  return Object.keys(step).filter((k) => ACTIONS.includes(k));
}

function describeTarget(t) {
  if (typeof t === 'string') return t;
  if (!isObj(t)) return String(t);
  const kind = TARGET_KINDS.find((k) => k in t);
  let s = kind === 'role' ? `role=${t.role}${t.name ? `[name="${t.name}"]` : ''}` : `${kind}=${JSON.stringify(t[kind])}`;
  if (Number.isInteger(t.nth)) s += ` (nth ${t.nth})`;
  return s;
}

function parseSize(v) {
  if (Array.isArray(v) && v.length === 2 && v.every((n) => Number.isInteger(n) && n > 0)) return v;
  if (typeof v === 'string') {
    const m = /^(\d+)x(\d+)$/.exec(v.trim());
    if (m) return [Number(m[1]), Number(m[2])];
  }
  return null;
}

// ── Shot-list validation ──────────────────────────────────────────────────

function validateTarget(where, t) {
  if (nonEmpty(t)) return [];
  if (!isObj(t)) return [`${where}: a target is a Playwright selector string or an object like {"role": "button", "name": "Save"}`];
  const kinds = TARGET_KINDS.filter((k) => k in t);
  if (kinds.length !== 1) return [`${where}: a target object needs exactly one of ${TARGET_KINDS.join(', ')} (got ${kinds.length ? kinds.join(', ') : 'none'})`];
  const errs = [];
  if (!nonEmpty(t[kinds[0]])) errs.push(`${where}: target "${kinds[0]}" must be a non-empty string`);
  if ('name' in t && kinds[0] !== 'role') errs.push(`${where}: "name" only applies to role targets`);
  if ('nth' in t && !(Number.isInteger(t.nth) && t.nth >= 0)) errs.push(`${where}: "nth" must be an integer ≥ 0`);
  for (const k of Object.keys(t)) {
    if (![...TARGET_KINDS, 'name', 'exact', 'nth'].includes(k)) errs.push(`${where}: unknown target key "${k}"`);
  }
  return errs;
}

function validateSteps(steps, label, touch) {
  const errors = [];
  const warnings = [];
  if (!Array.isArray(steps)) return { errors: [`"${label}" must be an array of steps`], warnings };
  steps.forEach((step, i) => {
    const where = `${label} ${i + 1}`;
    if (!isObj(step)) { errors.push(`${where}: must be an object like {"click": "..."}`); return; }
    const acts = stepAction(step);
    if (acts.length !== 1) {
      errors.push(`${where}: needs exactly one action (${ACTIONS.join(', ')}); got ${acts.length ? acts.join(', ') : 'none'}`);
      return;
    }
    const act = acts[0];
    const w = `${where} (${act})`;
    const v = step[act];
    for (const k of Object.keys(step)) {
      if (k !== act && !COMMON_KEYS.includes(k) && !ACTION_KEYS[act].includes(k)) errors.push(`${w}: unknown key "${k}"`);
    }
    if ('pause' in step && !(Number.isFinite(step.pause) && step.pause >= 0)) errors.push(`${w}: "pause" must be milliseconds ≥ 0`);
    if ('timeout' in step && !(Number.isFinite(step.timeout) && step.timeout > 0)) errors.push(`${w}: "timeout" must be milliseconds > 0`);
    if ('camera' in step && !(step.camera === false || (isObj(step.camera) && Number.isFinite(step.camera.scale) && step.camera.scale >= 1))) {
      errors.push(`${w}: "camera" must be false (no auto-zoom for this step) or {"scale": number ≥ 1}`);
    }
    switch (act) {
      case 'goto': if (!nonEmpty(v)) errors.push(`${w}: needs a URL or a path relative to "url"`); break;
      case 'click': case 'tap': case 'hover': case 'waitFor':
        errors.push(...validateTarget(w, v)); break;
      case 'type':
        if (v !== null && v !== true) errors.push(...validateTarget(w, v));
        if (typeof step.text !== 'string' || step.text === '') errors.push(`${w}: needs "text" to type`);
        if ('delay' in step && !(Number.isFinite(step.delay) && step.delay >= 0)) errors.push(`${w}: "delay" must be ms per key ≥ 0`);
        break;
      case 'press':
        if (!nonEmpty(v)) errors.push(`${w}: needs a key such as "Enter" or "Meta+K"`);
        break;
      case 'scroll':
        if (typeof v === 'number') {
          if (v === 0) errors.push(`${w}: scroll by a non-zero number of pixels (positive = down)`);
        } else errors.push(...validateTarget(w, v));
        if ('within' in step) errors.push(...validateTarget(`${w} within`, step.within));
        if ('by' in step) errors.push(`${w}: write the pixels as the action value, e.g. {"scroll": 600}`);
        break;
      case 'swipe':
        errors.push(...validateTarget(w, v));
        if (!['left', 'right', 'up', 'down'].includes(step.direction)) errors.push(`${w}: "direction" must be left, right, up or down`);
        if ('distance' in step && !(Number.isFinite(step.distance) && step.distance > 0)) errors.push(`${w}: "distance" must be px > 0`);
        if (!touch) warnings.push(`${w}: swipe on a desktop device is performed as a mouse drag`);
        break;
      case 'drag':
        errors.push(...validateTarget(w, v));
        errors.push(...validateTarget(`${w} to`, step.to));
        break;
      case 'select':
        errors.push(...validateTarget(w, v));
        if (!(typeof step.value === 'string' || (Array.isArray(step.value) && step.value.every((s) => typeof s === 'string')))) {
          errors.push(`${w}: needs "value" (an option value or label, or an array of them)`);
        }
        break;
      case 'wait':
        if (!(Number.isFinite(v) && v > 0)) errors.push(`${w}: needs milliseconds > 0; to wait for something to appear use waitFor`);
        else if (v > 10000) warnings.push(`${w}: a ${v} ms wait is dead air in the video; waitFor the thing you're waiting on`);
        break;
      case 'zoom':
        if (v !== 'out') errors.push(...validateTarget(w, v));
        if ('scale' in step && !(Number.isFinite(step.scale) && step.scale >= 1 && step.scale <= 6)) errors.push(`${w}: "scale" must be between 1 and 6`);
        if ('hold' in step && !(Number.isFinite(step.hold) && step.hold > 0)) errors.push(`${w}: "hold" must be ms > 0`);
        break;
      case 'mark': if (!nonEmpty(v)) errors.push(`${w}: needs a label`); break;
      default: break;
    }
    if (touch && act === 'hover') warnings.push(`${w}: touch devices have no hover; the step moves nothing on screen`);
    if (touch && act === 'drag') warnings.push(`${w}: drag on a touch device is performed as a touch drag`);
  });
  return { errors, warnings };
}

// Resolves the capture and output geometry. `devices` is Playwright's device
// table when available (needed only for named devices other than "desktop").
function resolveGeometry(shots, devices) {
  const errors = [];
  const device = shots.device ?? 'desktop';
  let ctx;
  let touch = false;
  let defaults;
  if (device === 'desktop') {
    ctx = { viewport: { ...DESKTOP.viewport }, deviceScaleFactor: DESKTOP.scale };
    defaults = DESKTOP;
  } else {
    const name = device === 'mobile' ? MOBILE_DEVICE : device;
    const d = devices ? devices[name] : null;
    if (devices && !d) {
      errors.push(`device "${device}" is not a Playwright device; use "desktop", "mobile" or a name from playwright's devices (e.g. "iPhone 15", "Pixel 7", "iPad Pro 11")`);
      return { errors };
    }
    if (!d) return { errors, unresolved: true };
    const { defaultBrowserType, ...rest } = d;
    ctx = { ...rest, viewport: { ...d.viewport } };
    touch = Boolean(d.hasTouch);
    const portrait = d.viewport.height >= d.viewport.width;
    defaults = { output: portrait ? MOBILE.output : DESKTOP.output, maxZoom: touch ? MOBILE.maxZoom : DESKTOP.maxZoom };
  }
  if (shots.viewport !== undefined) {
    const v = shots.viewport;
    if (!isObj(v) || !Number.isInteger(v.width) || !Number.isInteger(v.height) || v.width < 200 || v.height < 200) {
      errors.push('"viewport" must be {"width": int ≥ 200, "height": int ≥ 200} in CSS pixels');
    } else ctx.viewport = { width: v.width, height: v.height };
  }
  if (shots.scale !== undefined) {
    if (!(Number.isFinite(shots.scale) && shots.scale >= 1 && shots.scale <= 4)) errors.push('"scale" (device pixel ratio) must be between 1 and 4');
    else ctx.deviceScaleFactor = shots.scale;
  }
  const out = isObj(shots.output) ? shots.output : {};
  if (shots.output !== undefined && !isObj(shots.output)) errors.push('"output" must be an object like {"size": "1920x1080", "fps": 60}');
  const size = out.size === undefined ? defaults.output : parseSize(out.size);
  if (!size) errors.push('"output.size" must be "WIDTHxHEIGHT", e.g. "1920x1080"');
  else if (size.some((n) => n % 2)) errors.push('"output.size" must use even numbers (H.264 4:2:0 needs them)');
  const fps = out.fps ?? FPS;
  if (!(Number.isInteger(fps) && fps >= 24 && fps <= 60)) errors.push('"output.fps" must be an integer from 24 to 60');
  const zcfg = shots.zoom === undefined ? {} : shots.zoom;
  if (zcfg === false) { /* auto-zoom off */ } else if (!isObj(zcfg)) errors.push('"zoom" must be false or {"auto": bool, "max": number}');
  const autoZoom = zcfg !== false && zcfg.auto !== false;
  const maxZoom = isObj(zcfg) && zcfg.max !== undefined ? zcfg.max : defaults.maxZoom;
  if (!(Number.isFinite(maxZoom) && maxZoom >= 1 && maxZoom <= 4)) errors.push('"zoom.max" must be between 1 and 4');
  if (out.padding !== undefined && !(Number.isFinite(out.padding) && out.padding >= 0 && out.padding < 0.4)) {
    errors.push('"output.padding" must be a fraction of the frame between 0 and 0.4');
  }
  if (errors.length) return { errors };

  const [W, H] = size;
  const vw = ctx.viewport.width, vh = ctx.viewport.height;
  const dpr = ctx.deviceScaleFactor ?? 1;
  const sameAspect = Math.abs(W / H - vw / vh) / (vw / vh) < 0.01;
  const padding = out.padding ?? (sameAspect ? 0 : 0.06);
  const pad = Math.round(Math.min(W, H) * padding);
  const fit = Math.min((W - 2 * pad) / vw, (H - 2 * pad) / vh);
  const cw = Math.round(vw * fit), ch = Math.round(vh * fit);
  const content = { x: Math.round((W - cw) / 2), y: Math.round((H - ch) / 2), w: cw, h: ch };
  return {
    errors, device, touch, ctx, vw, vh, dpr, W, H, fps, content,
    framed: pad > 0, autoZoom, maxZoom,
    source: [Math.round(vw * dpr), Math.round(vh * dpr)],
  };
}

function resolutionWarnings(g, steps) {
  const warnings = [];
  const perPx = (z) => (g.source[0] / z) / g.content.w;
  if (perPx(1) < 1) {
    warnings.push(`the capture is ${g.source[0]}x${g.source[1]} but the video frame shows it ${g.content.w}px wide: ` +
      `it will look soft. Raise "scale" to ${Math.ceil((g.content.w / g.vw) * 10) / 10} or more, or lower "output.size"`);
  }
  let deepest = g.autoZoom ? g.maxZoom : 1;
  for (const s of steps) if (Number.isFinite(s?.scale) && 'zoom' in s) deepest = Math.max(deepest, s.scale);
  for (const s of steps) if (isObj(s?.camera) && Number.isFinite(s.camera.scale)) deepest = Math.max(deepest, s.camera.scale);
  if (perPx(deepest) < RESOLUTION_FLOOR) {
    const need = Math.ceil(((deepest * g.content.w * RESOLUTION_FLOOR) / g.vw) * 10) / 10;
    warnings.push(`at ${deepest}x zoom each output pixel gets ${perPx(deepest).toFixed(2)} captured pixels, so zoomed detail blurs. ` +
      `Raise "scale" to ${need} (needs ${need > 3 ? 'a fast machine' : 'nothing else'}) or lower the zoom`);
  }
  return warnings;
}

function validateShots(shots, devices) {
  const errors = [];
  const warnings = [];
  if (!isObj(shots)) return { errors: ['the shot list must be a JSON object with "url" and "steps"'], warnings };
  for (const k of Object.keys(shots)) if (!TOP_KEYS.includes(k)) errors.push(`unknown top-level key "${k}" (allowed: ${TOP_KEYS.join(', ')})`);
  if (!nonEmpty(shots.url)) errors.push('"url" is required: the page the recording starts on');
  else {
    try { new URL(shots.url); } catch { errors.push(`"url" must be absolute, e.g. http://127.0.0.1:3000/ (got ${shots.url})`); }
  }
  if (shots.colorScheme !== undefined && !['light', 'dark'].includes(shots.colorScheme)) errors.push('"colorScheme" must be light or dark');
  if (shots.storageState !== undefined && !nonEmpty(shots.storageState)) errors.push('"storageState" must be a path to a Playwright storage state file');
  if (shots.redact !== undefined && !(Array.isArray(shots.redact) && shots.redact.every(nonEmpty))) errors.push('"redact" must be an array of CSS selectors to blur');
  if (shots.scrollbars !== undefined && typeof shots.scrollbars !== 'boolean') errors.push('"scrollbars" must be true or false');
  if (shots.seed !== undefined && !Number.isInteger(shots.seed)) errors.push('"seed" must be an integer');
  if (shots.cursor !== undefined) {
    const c = shots.cursor;
    if (!isObj(c)) errors.push('"cursor" must be an object like {"size": 1.2, "click": "#3b82f6", "speed": 1}');
    else {
      if (c.size !== undefined && !(Number.isFinite(c.size) && c.size >= 0.5 && c.size <= 3)) errors.push('"cursor.size" must be between 0.5 and 3');
      if (c.speed !== undefined && !(Number.isFinite(c.speed) && c.speed >= 0.25 && c.speed <= 4)) errors.push('"cursor.speed" must be between 0.25 and 4 (higher is faster)');
      if (c.click !== undefined && !/^#[0-9a-fA-F]{6}$/.test(c.click)) errors.push('"cursor.click" must be a #rrggbb color');
      if (c.hidden !== undefined && typeof c.hidden !== 'boolean') errors.push('"cursor.hidden" must be true or false');
    }
  }
  if (shots.output?.background !== undefined && !/^#[0-9a-fA-F]{6}$/.test(shots.output.background)) errors.push('"output.background" must be a #rrggbb color');

  const g = resolveGeometry(shots, devices);
  errors.push(...g.errors);
  const touch = Boolean(g.touch);
  if (shots.setup !== undefined) {
    const r = validateSteps(shots.setup, 'setup step', touch);
    errors.push(...r.errors);
  }
  if (!Array.isArray(shots.steps) || shots.steps.length === 0) errors.push('"steps" must be a non-empty array: the interaction the video shows');
  else {
    const r = validateSteps(shots.steps, 'step', touch);
    errors.push(...r.errors);
    warnings.push(...r.warnings);
    const visible = shots.steps.filter((s) => isObj(s) && stepAction(s).some((a) => !['wait', 'waitFor', 'mark'].includes(a)));
    if (!visible.length) errors.push('no step does anything visible; a demo needs at least one click, tap, type, scroll or zoom');
  }
  if (!g.errors.length && !g.unresolved && Array.isArray(shots.steps)) warnings.push(...resolutionWarnings(g, shots.steps));
  if (g.unresolved) warnings.push(`device "${shots.device}" could not be resolved without playwright; resolution not checked`);
  return { errors, warnings, geometry: g };
}

// ── Playwright / ffmpeg discovery ─────────────────────────────────────────

function loadPlaywright({ required = true } = {}) {
  const bases = [path.join(process.cwd(), 'noop.js')];
  try {
    const root = execSync('npm root -g', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();
    if (root) bases.push(path.join(root, 'noop.js'));
  } catch { /* no npm */ }
  bases.push(import.meta.url.startsWith('file:') ? new URL(import.meta.url).pathname : __filename);
  for (const base of bases) {
    const req = createRequire(base);
    for (const name of ['playwright', 'playwright-core', '@playwright/test']) {
      try { return req(name); } catch { /* try next */ }
    }
  }
  if (!required) return null;
  throw new DemoError('playwright is not installed. Use the project\'s own (npm i -D playwright) or a global one ' +
    '(npm i -g playwright && npx playwright install chromium), then rerun', EXIT_MISSING_TOOL);
}

function preflightFfmpeg() {
  const r = spawnSync('ffmpeg', ['-hide_banner', '-encoders'], { encoding: 'utf8' });
  if (r.error) {
    throw new DemoError('ffmpeg not on PATH. Install it (macOS: brew install ffmpeg; Debian/Ubuntu: apt install ffmpeg) and rerun', EXIT_MISSING_TOOL);
  }
  if (!/libx264/.test(r.stdout)) throw new DemoError('this ffmpeg has no libx264 encoder; install a build with it (Homebrew\'s and Debian\'s have it)', EXIT_MISSING_TOOL);
}

async function launch(pw, g, { headed = false } = {}) {
  // --force-device-scale-factor makes the screencast deliver device pixels.
  // Without it Chromium screencasts (and Playwright's recordVideo) capture CSS
  // pixels: a 2x viewport records at half resolution.
  const args = [`--force-device-scale-factor=${g.dpr}`, '--hide-scrollbars'];
  const opts = { headless: !headed, args };
  if (process.env.BRUHS_CHROMIUM) opts.executablePath = process.env.BRUHS_CHROMIUM;
  try {
    return await pw.chromium.launch(opts);
  } catch (e) {
    if (/Executable doesn't exist|browserType\.launch/.test(String(e.message))) {
      throw new DemoError(`chromium could not start: ${String(e.message).split('\n')[0]}. Run: npx playwright install chromium ` +
        '(or set BRUHS_CHROMIUM to a Chrome binary)', EXIT_MISSING_TOOL);
    }
    throw e;
  }
}

function pageCss(shots) {
  let css = '';
  if (shots.scrollbars !== true) {
    css += 'html,body,*{scrollbar-width:none!important}::-webkit-scrollbar{display:none!important;width:0!important;height:0!important}';
  }
  for (const sel of shots.redact ?? []) css += `${sel}{filter:blur(12px)!important;user-select:none!important}`;
  return css;
}

async function newContext(browser, shots, g, baseDir) {
  const opts = { ...g.ctx, reducedMotion: 'no-preference' };
  if (shots.colorScheme) opts.colorScheme = shots.colorScheme;
  if (shots.storageState) {
    const p = path.resolve(baseDir, shots.storageState);
    if (!fs.existsSync(p)) throw new DemoError(`storageState file not found: ${p}`, EXIT_INVALID);
    opts.storageState = p;
  }
  const ctx = await browser.newContext(opts);
  const css = pageCss(shots);
  if (css) {
    await ctx.addInitScript((text) => {
      const add = () => {
        if (!document.documentElement || document.querySelector('style[data-bruhs-demo]')) return;
        const s = document.createElement('style');
        s.dataset.bruhsDemo = '1';
        s.textContent = text;
        document.documentElement.appendChild(s);
      };
      add();
      document.addEventListener('DOMContentLoaded', add);
    }, css);
  }
  return ctx;
}

// Redaction blurs pixels; the accessibility tree still holds the text. Hide
// redacted nodes from it before any snapshot leaves the browser.
async function ariaSnapshot(page, shots, timeout) {
  if (shots.redact?.length) {
    await page.evaluate((sels) => {
      for (const sel of sels) for (const el of document.querySelectorAll(sel)) el.setAttribute('aria-hidden', 'true');
    }, shots.redact).catch(() => {});
  }
  return page.locator('body').ariaSnapshot({ timeout });
}

function locate(page, t) {
  if (typeof t === 'string') return page.locator(t).first();
  const exact = t.exact === true ? { exact: true } : {};
  let loc;
  if ('role' in t) loc = page.getByRole(t.role, { ...(t.name ? { name: t.name } : {}), ...exact });
  else if ('text' in t) loc = page.getByText(t.text, exact);
  else if ('label' in t) loc = page.getByLabel(t.label, exact);
  else if ('placeholder' in t) loc = page.getByPlaceholder(t.placeholder, exact);
  else if ('testId' in t) loc = page.getByTestId(t.testId);
  else if ('alt' in t) loc = page.getByAltText(t.alt, exact);
  else if ('title' in t) loc = page.getByTitle(t.title, exact);
  else loc = page.locator(t.css);
  return Number.isInteger(t.nth) ? loc.nth(t.nth) : loc.first();
}

function resolveUrl(base, u) {
  try { return new URL(u, base).toString(); } catch { return u; }
}

// ── The director: performs steps like a person and logs a timeline ────────

class Director {
  constructor(page, cdp, shots, g) {
    this.page = page;
    this.cdp = cdp;
    this.shots = shots;
    this.g = g;
    this.rand = mulberry32(shots.seed ?? 7);
    this.speed = shots.cursor?.speed ?? 1;
    this.origin = null; // performance.now() at the first frame
    this.pos = { x: g.vw * 0.62, y: g.vh * 0.68 };
    this.tl = { moves: [], kinds: [{ t: 0, kind: 'arrow' }], clicks: [], touches: [], keys: [], focus: [], scrolls: [], navs: [], marks: [], steps: [] };
    this.recording = false;
  }

  t() { return this.origin === null ? 0 : Math.max(0, (performance.now() - this.origin) / 1000); }

  async box(loc, timeout) {
    await loc.waitFor({ state: 'visible', timeout });
    const b = await loc.boundingBox();
    if (!b) throw new Error('the target has no box on screen (detached or display:none)');
    return b;
  }

  // Bring a target into view with a visible scroll instead of a jump cut.
  async reveal(loc, timeout) {
    let b = await this.box(loc, timeout);
    const { vw, vh } = this.g;
    const margin = 48;
    const inView = b.y >= margin && b.y + b.height <= vh - margin && b.x >= 0 && b.x + b.width <= vw;
    if (inView || !this.recording) {
      if (!inView) { await loc.scrollIntoViewIfNeeded({ timeout }); b = await this.box(loc, timeout); }
      return b;
    }
    const dy = b.y + Math.min(b.height, vh * 0.5) / 2 - vh * 0.45;
    if (Math.abs(dy) > 4) await this.scrollBy(dy, null);
    b = await this.box(loc, timeout);
    const still = b.y < 0 || b.y + b.height > vh;
    if (still) { await loc.scrollIntoViewIfNeeded({ timeout }); b = await this.box(loc, timeout); }
    return b;
  }

  center(b) {
    return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
  }

  async cursorKindAt(x, y) {
    return this.page.evaluate(([px, py]) => {
      let el = document.elementFromPoint(px, py);
      while (el && el.shadowRoot && el.shadowRoot.elementFromPoint) {
        const inner = el.shadowRoot.elementFromPoint(px, py);
        if (!inner || inner === el) break;
        el = inner;
      }
      if (!el) return 'arrow';
      const c = getComputedStyle(el).cursor;
      if (c === 'pointer' || c === 'grab' || c === 'grabbing') return 'hand';
      if (c === 'text' || c === 'vertical-text') return 'ibeam';
      if (c === 'auto') {
        if (el.closest('a[href]')) return 'hand';
        const tag = el.tagName;
        const textInput = tag === 'TEXTAREA' || (tag === 'INPUT' && !['button', 'submit', 'reset', 'checkbox', 'radio', 'range', 'color', 'file', 'image'].includes(el.type));
        if (textInput || el.isContentEditable) return 'ibeam';
      }
      return 'arrow';
    }, [x, y]);
  }

  async moveTo(x, y, targetW = 40) {
    if (this.g.touch || !this.recording) { this.pos = { x, y }; return; }
    const from = { ...this.pos };
    const dist = Math.hypot(x - from.x, y - from.y);
    if (dist < 2) return;
    const dur = clamp(FITTS_A + FITTS_B * Math.log2(dist / Math.max(8, targetW) + 1), MOVE_MIN_S, MOVE_MAX_S) / this.speed;
    // Hand movement arcs: bend the path to one side by up to 12% of its length.
    const bend = (this.rand() * 2 - 1) * 0.12;
    const t0 = this.t();
    const start = performance.now();
    for (;;) {
      const u = (performance.now() - start) / 1000 / dur;
      if (u >= 1) break;
      const p = pathPoint(from, { x, y }, bend, minJerk(u));
      await this.page.mouse.move(p.x, p.y);
      await sleep(10);
    }
    await this.page.mouse.move(x, y);
    const t1 = this.t();
    this.tl.moves.push({ t0, t1: Math.max(t1, t0 + 0.05), from, to: { x, y }, bend });
    this.pos = { x, y };
    const kind = await this.cursorKindAt(x, y);
    const last = this.tl.kinds[this.tl.kinds.length - 1];
    if (kind !== last.kind) this.tl.kinds.push({ t: Math.max(t0, t1 - 0.08), kind });
  }

  async scrollBy(dy, within) {
    const { vw, vh, touch } = this.g;
    let at = within ?? (touch ? { x: vw / 2, y: vh * 0.6 } : this.pos);
    if (!touch && within) await this.moveTo(within.x, within.y, 200);
    at = { x: clamp(at.x, 4, vw - 4), y: clamp(at.y, 4, vh - 4) };
    const t0 = this.t();
    const travel = Math.abs(dy);
    await this.cdp.send('Input.synthesizeScrollGesture', {
      x: at.x, y: at.y, yDistance: -dy, speed: SCROLL_SPEED, preventFling: true,
      gestureSourceType: touch ? 'touch' : 'mouse', repeatCount: 0,
    });
    const t1 = this.t();
    this.tl.scrolls.push({ t0, t1 });
    if (touch && this.recording) {
      // The finger drags opposite to the scroll; long scrolls are several flicks
      // in reality, so show one drag capped to the visible screen.
      const len = Math.min(travel, vh * 0.55);
      const sign = dy > 0 ? -1 : 1;
      const y0 = clamp(at.y - (sign * len) / 2, 20, vh - 20);
      this.tl.touches.push({ t0, t1, from: { x: at.x, y: y0 }, to: { x: at.x, y: y0 + sign * len } });
    }
    await sleep(120);
  }

  focus(ev) { if (this.recording) this.tl.focus.push(ev); }

  async press(loc, b, step, timeout) {
    // Aim a little off-center like a person would, but stay inside the target.
    const c = this.center(b);
    const jx = (this.rand() - 0.5) * Math.min(b.width * 0.2, 12);
    const jy = (this.rand() - 0.5) * Math.min(b.height * 0.2, 6);
    const x = c.x + jx, y = c.y + jy;
    const t0 = this.t();
    await this.moveTo(x, y, Math.min(b.width, b.height));
    if (this.recording && !this.g.touch) await sleep(DWELL_BEFORE_CLICK_MS / this.speed);
    const position = { x: x - b.x, y: y - b.y };
    const ta = this.t();
    if (this.g.touch) {
      await loc.tap({ position, timeout });
      if (this.recording) this.tl.touches.push({ t0: ta, t1: ta + 0.1, from: { x, y }, to: { x, y } });
    } else {
      await loc.click({ position, delay: CLICK_HOLD_MS, timeout });
      if (this.recording) this.tl.clicks.push({ t: ta, up: ta + CLICK_HOLD_MS / 1000, x, y });
    }
    return { t0, ta };
  }

  async run(step, index, baseUrl) {
    const act = stepAction(step)[0];
    const v = step[act];
    const timeout = step.timeout ?? 10000;
    const pause = step.pause ?? (act === 'wait' || act === 'waitFor' || act === 'mark' ? 0 : STEP_PAUSE_MS);
    const record = { index, action: act, target: ['wait', 'press', 'mark', 'goto', 'scroll'].includes(act) && typeof v !== 'object' ? v : describeTarget(v), start: this.t() };
    const cam = step.camera;
    const zoomable = cam !== false;
    const camScale = isObj(cam) ? cam.scale : undefined;
    const page = this.page;
    switch (act) {
      case 'goto': {
        const t = this.t();
        await page.goto(resolveUrl(baseUrl, v), { waitUntil: 'load', timeout: Math.max(timeout, 30000) });
        this.tl.navs.push({ t });
        break;
      }
      case 'click': case 'tap': {
        const loc = locate(page, v);
        const b = await this.reveal(loc, timeout);
        const { t0, ta } = await this.press(loc, b, step, timeout);
        if (zoomable) this.focus({ t0, ta, t1: this.t() + pause / 1000, rect: b, scale: camScale, step: index });
        break;
      }
      case 'hover': {
        const loc = locate(page, v);
        const b = await this.reveal(loc, timeout);
        const t0 = this.t();
        const c = this.center(b);
        await this.moveTo(c.x, c.y, Math.min(b.width, b.height));
        if (!this.g.touch) await loc.hover({ position: { x: c.x - b.x, y: c.y - b.y }, timeout });
        if (zoomable) this.focus({ t0, ta: this.t(), t1: this.t() + pause / 1000, rect: b, scale: camScale, step: index });
        break;
      }
      case 'type': {
        let t0 = this.t();
        let ta = t0;
        let rect = null;
        if (v !== null && v !== true) {
          const loc = locate(page, v);
          const b = await this.reveal(loc, timeout);
          ({ t0, ta } = await this.press(loc, b, step, timeout));
          rect = b;
          if (step.clear) await loc.fill('', { timeout });
        }
        const base = step.delay ?? TYPE_DELAY_MS;
        // Long text types faster, the way people speed up mid-word.
        const scale = step.text.length > 40 ? 0.6 : 1;
        for (const ch of step.text) {
          await page.keyboard.type(ch);
          if (this.recording && base > 0) await sleep((base + (this.rand() - 0.5) * TYPE_JITTER_MS) * scale);
        }
        if (rect && zoomable) this.focus({ t0, ta, t1: this.t() + pause / 1000, rect, scale: camScale, step: index });
        break;
      }
      case 'press': {
        const t = this.t();
        await page.keyboard.press(v);
        if (this.recording) this.tl.keys.push({ t, label: keyLabel(v) });
        break;
      }
      case 'scroll': {
        let within = null;
        if (step.within) {
          const wb = await this.box(locate(page, step.within), timeout);
          within = this.center(wb);
        }
        if (typeof v === 'number') await this.scrollBy(v, within);
        else await this.reveal(locate(page, v), timeout);
        break;
      }
      case 'swipe': {
        const loc = locate(page, v);
        const b = await this.reveal(loc, timeout);
        const c = this.center(b);
        const dist = step.distance ?? Math.min(240, (step.direction === 'left' || step.direction === 'right' ? b.width : b.height) * 0.7);
        const d = { left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1] }[step.direction];
        const from = { x: c.x - (d[0] * dist) / 2, y: c.y - (d[1] * dist) / 2 };
        const to = { x: c.x + (d[0] * dist) / 2, y: c.y + (d[1] * dist) / 2 };
        const t0 = this.t();
        await this.drag(from, to, 0.28);
        if (zoomable) this.focus({ t0, ta: t0, t1: this.t() + pause / 1000, rect: b, scale: camScale, step: index });
        break;
      }
      case 'drag': {
        const sb = await this.reveal(locate(page, v), timeout);
        const tb = await this.box(locate(page, step.to), timeout);
        const t0 = this.t();
        await this.drag(this.center(sb), this.center(tb), null);
        if (zoomable) this.focus({ t0, ta: t0, t1: this.t() + pause / 1000, rect: unionRect(sb, tb), scale: camScale, step: index });
        break;
      }
      case 'select': {
        const loc = locate(page, v);
        const b = await this.reveal(loc, timeout);
        const c = this.center(b);
        const t0 = this.t();
        await this.moveTo(c.x, c.y, Math.min(b.width, b.height));
        const ta = this.t();
        if (this.recording) {
          if (this.g.touch) this.tl.touches.push({ t0: ta, t1: ta + 0.1, from: c, to: c });
          else this.tl.clicks.push({ t: ta, up: ta + CLICK_HOLD_MS / 1000, x: c.x, y: c.y });
        }
        // A native <select> popup is drawn outside the page and never reaches
        // the screencast, so choose the option directly after the visible click.
        await loc.selectOption(step.value, { timeout });
        if (zoomable) this.focus({ t0, ta, t1: this.t() + pause / 1000, rect: b, scale: camScale, step: index });
        break;
      }
      case 'wait': await sleep(v); break;
      case 'waitFor': await locate(page, v).waitFor({ state: 'visible', timeout }); break;
      case 'zoom': {
        if (v === 'out') { this.tl.focus.push({ out: true, t0: this.t() }); await sleep(ZOOM_OUT_S * 1000); break; }
        const loc = locate(page, v);
        const b = await this.reveal(loc, timeout);
        // "hold" counts from when the camera arrives, not from when it starts moving.
        const hold = step.hold ?? EXPLICIT_HOLD_MS;
        const t0 = this.t();
        this.tl.focus.push({ explicit: true, t0, ta: t0, t1: t0 + ZOOM_IN_S + hold / 1000, rect: b, scale: step.scale, step: index });
        await sleep(ZOOM_IN_S * 1000 + hold);
        break;
      }
      case 'mark': this.tl.marks.push({ t: this.t(), label: v }); break;
      default: break;
    }
    if (pause) await sleep(pause);
    record.end = this.t();
    this.tl.steps.push(record);
  }

  async drag(from, to, seconds) {
    const page = this.page;
    if (this.g.touch) {
      const dur = seconds ?? 0.5;
      const t0 = this.t();
      const send = (type, p) => this.cdp.send('Input.dispatchTouchEvent', { type, touchPoints: p ? [{ x: p.x, y: p.y }] : [] });
      await send('touchStart', from);
      const start = performance.now();
      for (;;) {
        const u = (performance.now() - start) / 1000 / dur;
        if (u >= 1) break;
        const s = minJerk(u);
        await send('touchMove', { x: from.x + (to.x - from.x) * s, y: from.y + (to.y - from.y) * s });
        await sleep(12);
      }
      await send('touchMove', to);
      await send('touchEnd', null);
      if (this.recording) this.tl.touches.push({ t0, t1: this.t(), from, to });
      return;
    }
    await this.moveTo(from.x, from.y, 40);
    await sleep(DWELL_BEFORE_CLICK_MS / this.speed);
    const down = this.t();
    await page.mouse.down();
    await sleep(120);
    const saved = this.speed;
    this.speed = saved * 0.7; // carrying something is slower than pointing
    await this.moveTo(to.x, to.y, 60);
    this.speed = saved;
    await sleep(100);
    await page.mouse.up();
    if (this.recording) this.tl.clicks.push({ t: down, up: this.t(), x: from.x, y: from.y, drag: true });
  }
}

function minJerk(u) {
  // Minimum-jerk profile: the velocity curve of a human reaching movement.
  const s = clamp(u, 0, 1);
  return s * s * s * (10 - 15 * s + 6 * s * s);
}

function pathPoint(a, b, bend, s) {
  const dx = b.x - a.x, dy = b.y - a.y;
  const cx = (a.x + b.x) / 2 - dy * bend, cy = (a.y + b.y) / 2 + dx * bend;
  const m = 1 - s;
  return { x: m * m * a.x + 2 * m * s * cx + s * s * b.x, y: m * m * a.y + 2 * m * s * cy + s * s * b.y };
}

function unionRect(a, b) {
  const x = Math.min(a.x, b.x), y = Math.min(a.y, b.y);
  return { x, y, width: Math.max(a.x + a.width, b.x + b.width) - x, height: Math.max(a.y + a.height, b.y + b.height) - y };
}

const KEY_GLYPHS = {
  meta: '⌘', cmd: '⌘', command: '⌘', control: 'Ctrl', ctrl: 'Ctrl', alt: '⌥', option: '⌥', shift: '⇧',
  enter: '↵ Enter', return: '↵ Return', escape: 'Esc', esc: 'Esc', backspace: '⌫', delete: '⌦', tab: '⇥ Tab',
  arrowup: '↑', arrowdown: '↓', arrowleft: '←', arrowright: '→', space: 'Space', ' ': 'Space',
  controlormeta: process.platform === 'darwin' ? '⌘' : 'Ctrl',
};
function keyLabel(combo) {
  return combo.split('+').map((k) => KEY_GLYPHS[k.toLowerCase()] ?? (k.length === 1 ? k.toUpperCase() : k)).join(' ');
}

// ── Camera planning ───────────────────────────────────────────────────────

function fitZoom(rect, vw, vh, pad) {
  return Math.min(vw / (rect.width + vw * pad), vh / (rect.height + vh * pad));
}

function clampCenter(c, z, vw, vh) {
  const hw = vw / (2 * z), hh = vh / (2 * z);
  return { x: clamp(c.x, hw, vw - hw), y: clamp(c.y, hh, vh - hh) };
}

// Turns focus events into camera keyframes {t, z, x, y}. Between keyframes
// the compositor eases; equal neighbours hold.
export function planCamera(tl, g, end) {
  const { vw, vh } = g;
  const home = { t: 0, z: 1, x: vw / 2, y: vh / 2 };
  const keys = [home];
  const breakers = [...tl.scrolls.map((s) => s.t0), ...tl.navs.map((n) => n.t)].sort((a, b) => a - b);
  const outs = tl.focus.filter((f) => f.out).map((f) => f.t0);
  const events = tl.focus.filter((f) => !f.out && (f.explicit || g.autoZoom)).sort((a, b) => a.t0 - b.t0);

  const groups = [];
  for (const ev of events) {
    const gr = groups[groups.length - 1];
    const broken = gr && [...breakers, ...outs].some((b) => b >= gr.lastTa && b <= ev.ta);
    const join = gr && !ev.explicit && !gr.explicit && !broken && ev.t0 - gr.end <= GROUP_GAP_S;
    if (join) { gr.events.push(ev); gr.end = Math.max(gr.end, ev.t1); gr.lastTa = ev.ta; gr.union = unionRect(gr.union, ev.rect); }
    else groups.push({ events: [ev], explicit: Boolean(ev.explicit), end: ev.t1, lastTa: ev.ta, union: ev.rect });
  }

  const shots = [];
  for (const gr of groups) {
    let z;
    const override = gr.events.map((e) => e.scale).filter(Number.isFinite);
    if (gr.explicit) z = override[0] ?? clamp(fitZoom(gr.union, vw, vh, 0.15), 1.2, 3);
    else if (override.length) z = Math.max(...override);
    else {
      // Frame the whole run of actions if that still reads as a zoom; when the
      // actions are spread out, zoom to a typical one and pan between them.
      const whole = fitZoom(gr.union, vw, vh, FIT_PAD);
      const each = gr.events.map((e) => fitZoom(e.rect, vw, vh, FIT_PAD)).sort((a, b) => a - b);
      z = Math.min(g.maxZoom, whole >= MIN_ZOOM ? whole : each[Math.floor(each.length / 2)]);
    }
    if (!(z >= MIN_ZOOM)) continue;
    const fits = gr.union.width * z <= vw * 0.86 && gr.union.height * z <= vh * 0.86;
    const unionC = { x: gr.union.x + gr.union.width / 2, y: gr.union.y + gr.union.height / 2 };
    const targets = fits ? [{ ev: gr.events[0], c: unionC }] : gr.events.map((e) => ({ ev: e, c: { x: e.rect.x + e.rect.width / 2, y: e.rect.y + e.rect.height / 2 } }));
    shots.push({ ...gr, z, targets });
  }

  const last = () => keys[keys.length - 1];
  const hold = (t) => { if (t > last().t + 1e-3) keys.push({ ...last(), t }); };
  const go = (t, z, c) => {
    const cc = clampCenter(c, z, vw, vh);
    keys.push({ t: Math.max(t, last().t + 0.05), z, x: cc.x, y: cc.y });
  };

  shots.forEach((s, i) => {
    s.targets.forEach((tg, j) => {
      const arrive = tg.ev.explicit ? tg.ev.t0 + ZOOM_IN_S : tg.ev.ta;
      const span = j === 0 ? ZOOM_IN_S : PAN_S;
      const startT = Math.max(last().t, arrive - span, j === 0 ? 0 : tg.ev.t0 - 0.1);
      hold(startT);
      go(Math.max(arrive, startT + 0.3), s.z, tg.c);
    });
    let outStart = s.end + (s.explicit ? 0 : LINGER_S);
    const nextBreak = [...breakers, ...outs].find((b) => b > s.lastTa);
    if (nextBreak !== undefined) outStart = Math.min(outStart, nextBreak - ZOOM_OUT_S * 0.6);
    outStart = Math.max(outStart, last().t);
    const next = shots[i + 1];
    if (next) {
      const nextArrive = next.targets[0].ev.explicit ? next.targets[0].ev.t0 + ZOOM_IN_S : next.targets[0].ev.ta;
      const between = [...breakers, ...outs].some((b) => b > s.lastTa && b < nextArrive);
      // Close shots cut straight across instead of zooming out and back in.
      if (!between && nextArrive - ZOOM_IN_S < outStart + ZOOM_OUT_S) { hold(Math.min(outStart, nextArrive - ZOOM_IN_S)); return; }
    }
    hold(outStart);
    go(Math.min(outStart + ZOOM_OUT_S, Math.max(end, outStart + 0.3)), 1, { x: vw / 2, y: vh / 2 });
  });
  hold(end);
  return { keys, shots: shots.map((s) => ({ t: s.targets[0].ev.ta, z: Number(s.z.toFixed(2)), steps: s.events.map((e) => e.step) })) };
}

// ── Compositor (runs in a second, offscreen Chromium page) ────────────────

const CURSORS = {
  // 32-unit artboards; hot = the click point.
  arrow: {
    hot: [7, 4],
    svg: '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 32 32"><path d="M7 4 L7 24.5 L12.2 19.6 L15.6 27.4 L19 26 L15.6 18.4 L22.6 18.4 Z" fill="#111" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/></svg>',
  },
  hand: {
    hot: [13, 4],
    svg: '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 32 32"><path d="M13 4c-1.2 0-2.1.9-2.1 2.1v10.1l-1.6-1.7c-.9-.9-2.3-.9-3.1-.1-.8.7-.9 2-.2 2.9l4.8 6.4c1.4 1.8 3.4 2.9 5.7 2.9h2.8c3.6 0 6.5-2.9 6.5-6.5v-5.4c0-1.1-.9-2-2-2-.5 0-.9.2-1.3.5 0-1.1-.9-2-2-2-.6 0-1.1.3-1.5.7-.3-.8-1-1.4-1.9-1.4-.5 0-.9.2-1.3.4V6.1C15.1 4.9 14.2 4 13 4z" fill="#fff" stroke="#111" stroke-width="1.5" stroke-linejoin="round"/><path d="M15.1 14.5v4.5M18.4 15.2v3.8M21.6 16v3" stroke="#111" stroke-width="1.2" stroke-linecap="round"/></svg>',
  },
  ibeam: {
    hot: [16, 16],
    svg: '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 32 32"><g fill="none" stroke-linecap="round"><path d="M12 6.5h2.2c.8 0 1.4.4 1.8.9.4-.5 1-.9 1.8-.9H20M16 7.5v17M12 25.5h2.2c.8 0 1.4-.4 1.8-.9.4.5 1 .9 1.8.9H20M13.5 16h5" stroke="#fff" stroke-width="4"/><path d="M12 6.5h2.2c.8 0 1.4.4 1.8.9.4-.5 1-.9 1.8-.9H20M16 7.5v17M12 25.5h2.2c.8 0 1.4-.4 1.8-.9.4.5 1 .9 1.8.9H20M13.5 16h5" stroke="#111" stroke-width="1.6"/></g></svg>',
  },
};

const COMPOSITOR_HTML = `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#000}</style></head>
<body><canvas id="c"></canvas><script>
const ease = (u) => { const s = Math.min(1, Math.max(0, u)); return s * s * s * (s * (s * 6 - 15) + 10); };
const minJerk = (u) => { const s = Math.min(1, Math.max(0, u)); return s * s * s * (10 - 15 * s + 6 * s * s); };
let P, canvas, ctx, cursorImgs = {}, cache = { i: -1, bmp: null }, lastKey = '';
window.setup = async (plan) => {
  P = plan;
  canvas = document.getElementById('c');
  canvas.width = P.W; canvas.height = P.H;
  ctx = canvas.getContext('2d');
  ctx.imageSmoothingQuality = 'high';
  for (const [k, c] of Object.entries(P.cursors)) {
    const img = new Image();
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(c.svg);
    await img.decode();
    cursorImgs[k] = { img, hot: c.hot };
  }
  return true;
};
function frameIndexAt(t) {
  const f = P.frames; let lo = 0, hi = f.length - 1;
  if (t <= f[0]) return 0;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (f[mid] <= t) lo = mid; else hi = mid - 1; }
  return lo;
}
async function bitmap(i) {
  if (cache.i === i) return cache.bmp;
  const blob = await (await fetch('http://bruhs.demo/frame/' + i)).blob();
  const bmp = await createImageBitmap(blob);
  if (cache.bmp) cache.bmp.close();
  cache = { i, bmp };
  return bmp;
}
function camera(t) {
  const k = P.camera; if (t <= k[0].t) return k[0];
  for (let i = 0; i < k.length - 1; i++) {
    const a = k[i], b = k[i + 1];
    if (t <= b.t) {
      const s = ease((t - a.t) / Math.max(1e-6, b.t - a.t));
      const z = Math.exp(Math.log(a.z) + (Math.log(b.z) - Math.log(a.z)) * s);
      return { z, x: a.x + (b.x - a.x) * s, y: a.y + (b.y - a.y) * s };
    }
  }
  return k[k.length - 1];
}
function cursorPos(t) {
  let pos = P.cursorStart;
  for (const m of P.moves) {
    if (t < m.t0) break;
    if (t <= m.t1) {
      const s = minJerk((t - m.t0) / (m.t1 - m.t0));
      const dx = m.to.x - m.from.x, dy = m.to.y - m.from.y;
      const cx = (m.from.x + m.to.x) / 2 - dy * m.bend, cy = (m.from.y + m.to.y) / 2 + dx * m.bend;
      const n = 1 - s;
      return { x: n * n * m.from.x + 2 * n * s * cx + s * s * m.to.x, y: n * n * m.from.y + 2 * n * s * cy + s * s * m.to.y };
    }
    pos = m.to;
  }
  return pos;
}
function cursorKind(t) { let k = 'arrow'; for (const c of P.kinds) { if (c.t <= t) k = c.kind; else break; } return k; }
function roundRect(x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
window.render = async (from, count) => {
  const out = [];
  for (let k = from; k < from + count && k < P.total; k++) out.push(await frame(k));
  return out;
};
async function frame(k) {
  const t = k / P.fps;
  const fi = frameIndexAt(t + P.lag);
  const cam = camera(t);
  const C = P.content, vw = P.vw, vh = P.vh;
  const sx = C.w / vw;                       // output px per CSS px at zoom 1
  const x0 = cam.x - vw / (2 * cam.z), y0 = cam.y - vh / (2 * cam.z);
  const toOut = (p) => ({ x: C.x + (p.x - x0) * cam.z * sx, y: C.y + (p.y - y0) * cam.z * sx });

  // Effects alive at t.
  const cur = P.cursorHidden ? null : cursorPos(t);
  const kind = cursorKind(t);
  let press = 0; const ripples = [];
  for (const c of P.clicks) {
    if (t >= c.t && t <= c.up) press = 1;
    else if (t > c.up && t < c.up + 0.15) press = Math.max(press, 1 - (t - c.up) / 0.15);
    else if (t >= c.t - 0.06 && t < c.t) press = Math.max(press, (t - (c.t - 0.06)) / 0.06);
    if (!c.drag && t >= c.t && t < c.t + 0.5) ripples.push({ p: c, u: (t - c.t) / 0.5 });
  }
  const touches = [];
  for (const tc of P.touches) {
    if (t < tc.t0 - 0.08 || t > tc.t1 + 0.3) continue;
    const s = minJerk((t - tc.t0) / Math.max(1e-3, tc.t1 - tc.t0));
    const p = { x: tc.from.x + (tc.to.x - tc.from.x) * s, y: tc.from.y + (tc.to.y - tc.from.y) * s };
    const a = t < tc.t0 ? (t - (tc.t0 - 0.08)) / 0.08 : t > tc.t1 ? 1 - (t - tc.t1) / 0.3 : 1;
    const grow = t < tc.t0 ? 0.7 + 0.3 * a : t > tc.t1 ? 1 + 0.35 * (t - tc.t1) / 0.3 : 1;
    touches.push({ p, a, grow, trail: tc.from, moving: Math.hypot(tc.to.x - tc.from.x, tc.to.y - tc.from.y) > 4 });
  }
  let chip = null;
  for (const kc of P.keys) if (t >= kc.t - 0.05 && t < kc.t + 1.4) chip = kc;

  const key = [fi, cam.z.toFixed(4), cam.x.toFixed(2), cam.y.toFixed(2), cur ? cur.x.toFixed(2) + ',' + cur.y.toFixed(2) : '', kind,
    press.toFixed(3), ripples.map((r) => r.u.toFixed(3)).join(), touches.map((r) => r.a.toFixed(3) + r.p.x.toFixed(1) + r.p.y.toFixed(1)).join(),
    chip ? chip.label + Math.min(1, (t - chip.t + 0.05) / 0.12).toFixed(2) + Math.min(1, (chip.t + 1.4 - t) / 0.25).toFixed(2) : ''].join('|');
  if (key === lastKey) return null;
  lastKey = key;

  // Background and frame.
  ctx.fillStyle = P.background; ctx.fillRect(0, 0, P.W, P.H);
  const radius = P.framed ? (P.touch ? 0.06 : 0.012) * Math.min(C.w, C.h * 2) : 0;
  ctx.save();
  if (P.framed) {
    ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = 48; ctx.shadowOffsetY = 18;
    roundRect(C.x, C.y, C.w, C.h, radius); ctx.fillStyle = '#000'; ctx.fill();
    ctx.shadowColor = 'transparent';
  }
  roundRect(C.x, C.y, C.w, C.h, radius); ctx.clip();
  const bmp = await bitmap(fi);
  const d = bmp.width / vw;                  // captured px per CSS px
  ctx.drawImage(bmp, x0 * d, y0 * d, (vw / cam.z) * d, (vh / cam.z) * d, C.x, C.y, C.w, C.h);

  const unit = cam.z * sx;                   // output px per CSS px now
  for (const r of ripples) {
    const p = toOut(r.p);
    ctx.beginPath(); ctx.arc(p.x, p.y, (8 + 26 * ease(r.u)) * unit, 0, Math.PI * 2);
    ctx.strokeStyle = P.clickColor + Math.round((1 - r.u) * 200).toString(16).padStart(2, '0');
    ctx.lineWidth = 3 * unit; ctx.stroke();
    ctx.beginPath(); ctx.arc(p.x, p.y, (8 + 18 * ease(r.u)) * unit, 0, Math.PI * 2);
    ctx.fillStyle = P.clickColor + Math.round((1 - r.u) * 60).toString(16).padStart(2, '0'); ctx.fill();
  }
  for (const tc of touches) {
    const p = toOut(tc.p), rad = 21 * unit * tc.grow;
    if (tc.moving) {
      const a = toOut(tc.trail);
      const grad = ctx.createLinearGradient(a.x, a.y, p.x, p.y);
      grad.addColorStop(0, 'rgba(255,255,255,0)'); grad.addColorStop(1, 'rgba(255,255,255,' + (0.35 * tc.a) + ')');
      ctx.strokeStyle = grad; ctx.lineWidth = rad * 1.2; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(p.x, p.y); ctx.stroke();
    }
    ctx.beginPath(); ctx.arc(p.x, p.y, rad, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(20,20,20,' + (0.22 * tc.a) + ')'; ctx.fill();
    ctx.lineWidth = Math.max(2, 2.2 * unit); ctx.strokeStyle = 'rgba(255,255,255,' + (0.9 * tc.a) + ')'; ctx.stroke();
  }
  if (cur) {
    const ci = cursorImgs[kind];
    const size = 30 * P.cursorSize * Math.sqrt(cam.z) * sx * (1 - 0.14 * press);
    const p = toOut(cur);
    ctx.shadowColor = 'rgba(0,0,0,0.3)'; ctx.shadowBlur = size * 0.18; ctx.shadowOffsetY = size * 0.06;
    ctx.drawImage(ci.img, p.x - (ci.hot[0] / 32) * size, p.y - (ci.hot[1] / 32) * size, size, size);
    ctx.shadowColor = 'transparent';
  }
  ctx.restore();

  if (chip) {
    const a = Math.min(1, (t - chip.t + 0.05) / 0.12, (chip.t + 1.4 - t) / 0.25);
    const fs = Math.round(Math.min(P.W, P.H) * 0.035);
    ctx.font = '600 ' + fs + 'px -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif';
    const w = ctx.measureText(chip.label).width + fs * 1.4, h = fs * 1.9;
    const x = (P.W - w) / 2, y = P.H - h - Math.min(P.W, P.H) * 0.06 + (1 - a) * fs * 0.5;
    ctx.globalAlpha = a;
    roundRect(x, y, w, h, h * 0.28); ctx.fillStyle = 'rgba(17,17,17,0.82)'; ctx.fill();
    ctx.lineWidth = 1.5; ctx.strokeStyle = 'rgba(255,255,255,0.18)'; ctx.stroke();
    ctx.fillStyle = '#fff'; ctx.textBaseline = 'middle'; ctx.textAlign = 'center';
    ctx.fillText(chip.label, P.W / 2, y + h / 2 + fs * 0.04);
    ctx.globalAlpha = 1;
  }
  const blob = await new Promise((r) => canvas.toBlob(r, 'image/jpeg', 0.94));
  return await new Promise((r) => { const fr = new FileReader(); fr.onload = () => r(fr.result.slice(fr.result.indexOf(',') + 1)); fr.readAsDataURL(blob); });
}
</script></body></html>`;

async function compose(pw, g, shots, tl, frames, framesDir, duration, outFile) {
  const browser = await pw.chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: Math.min(g.W, 1920), height: Math.min(g.H, 1920) }, deviceScaleFactor: 1 });
  await page.route('http://bruhs.demo/**', async (route) => {
    const u = new URL(route.request().url());
    if (u.pathname === '/') return route.fulfill({ contentType: 'text/html', body: COMPOSITOR_HTML });
    const m = /^\/frame\/(\d+)$/.exec(u.pathname);
    if (m) return route.fulfill({ contentType: 'image/jpeg', path: path.join(framesDir, frames[Number(m[1])].file) });
    return route.fulfill({ status: 404, body: '' });
  });
  await page.goto('http://bruhs.demo/');
  const camera = planCamera(tl, g, duration);
  const total = Math.max(1, Math.round(duration * g.fps));
  await page.evaluate((plan) => window.setup(plan), {
    W: g.W, H: g.H, vw: g.vw, vh: g.vh, fps: g.fps, total, content: g.content, framed: g.framed, touch: g.touch,
    background: shots.output?.background ?? '#16181d',
    clickColor: shots.cursor?.click ?? '#3b82f6',
    cursorSize: shots.cursor?.size ?? 1,
    cursorHidden: g.touch || shots.cursor?.hidden === true,
    cursorStart: tl.cursorStart,
    // Frames reach Node ~1 frame after Chromium paints them; look slightly
    // ahead so effects line up with the pixels they cause.
    lag: 0.016,
    frames: frames.map((f) => f.t), camera: camera.keys, moves: tl.moves, kinds: tl.kinds, clicks: tl.clicks,
    touches: tl.touches, keys: tl.keys, cursors: CURSORS,
  });

  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-c:v', 'mjpeg', '-framerate', String(g.fps), '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', String(g.fps),
    '-movflags', '+faststart', outFile], { stdio: ['pipe', 'ignore', 'pipe'] });
  let ffErr = '';
  ff.stderr.on('data', (d) => { ffErr += d; });
  const ffDone = new Promise((resolve) => ff.on('close', resolve));
  let pipeError = null;
  ff.stdin.on('error', (e) => { pipeError = e; });
  const write = (buf) => new Promise((resolve, reject) => {
    if (pipeError) return reject(new DemoError(`ffmpeg stopped reading frames: ${ffErr.trim() || pipeError.message}`, EXIT_FAILED));
    if (ff.stdin.write(buf)) resolve(); else ff.stdin.once('drain', resolve);
  });
  let prev = null;
  const BATCH = 12;
  for (let k = 0; k < total; k += BATCH) {
    const out = await page.evaluate(([a, n]) => window.render(a, n), [k, BATCH]);
    for (const b64 of out) {
      if (b64) prev = Buffer.from(b64, 'base64');
      await write(prev);
    }
  }
  ff.stdin.end();
  const code = await ffDone;
  await browser.close();
  if (code !== 0) throw new DemoError(`ffmpeg failed encoding the video:\n${ffErr.trim()}`, EXIT_FAILED);
  return camera;
}

// ── Recording ─────────────────────────────────────────────────────────────

async function record(shots, baseDir, outDir, opts, pw) {
  const { errors, warnings, geometry: g } = validateShots(shots, pw.devices);
  if (errors.length) throw new DemoError(`the shot list has problems:\n${errors.map((e) => `  - ${e}`).join('\n')}`, EXIT_INVALID);
  preflightFfmpeg();
  for (const w of warnings) process.stderr.write(`warning: ${w}\n`);

  fs.mkdirSync(outDir, { recursive: true });
  const work = path.join(outDir, 'work');
  fs.rmSync(work, { recursive: true, force: true });
  const framesDir = path.join(work, 'frames');
  fs.mkdirSync(framesDir, { recursive: true });

  const browser = await launch(pw, g, { headed: opts.headed });
  let director;
  const frames = [];
  let failure = null;
  try {
    const context = await newContext(browser, shots, g, baseDir);
    const page = await context.newPage();
    const cdp = await context.newCDPSession(page);
    director = new Director(page, cdp, shots, g);

    await page.goto(shots.url, { waitUntil: 'load', timeout: 30000 });
    for (const [i, step] of (shots.setup ?? []).entries()) {
      try { await director.run({ ...step, pause: step.pause ?? 0 }, i + 1, shots.url); } catch (e) {
        failure = { phase: 'setup', index: i + 1, step, error: e };
        break;
      }
    }
    if (!failure) {
      await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
      // Park the real mouse where the drawn cursor starts so hover states agree.
      if (!g.touch) await page.mouse.move(director.pos.x, director.pos.y);
      let firstFrame;
      const gotFirst = new Promise((r) => { firstFrame = r; });
      cdp.on('Page.screencastFrame', (f) => {
        cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
        const now = performance.now();
        if (director.origin === null) director.origin = now;
        const file = `${String(frames.length).padStart(6, '0')}.jpg`;
        fs.writeFileSync(path.join(framesDir, file), Buffer.from(f.data, 'base64'));
        frames.push({ t: (now - director.origin) / 1000, file });
        firstFrame();
      });
      await cdp.send('Page.startScreencast', { format: 'jpeg', quality: JPEG_QUALITY, maxWidth: g.source[0], maxHeight: g.source[1], everyNthFrame: 1 });
      // An idle page sends no frames; nudge a repaint so the clip has a first frame.
      await page.evaluate(() => { document.documentElement.style.outline = '0px solid transparent'; requestAnimationFrame(() => { document.documentElement.style.outline = ''; }); });
      await Promise.race([gotFirst, sleep(3000)]);
      if (!frames.length) throw new DemoError('Chromium sent no screencast frames; the page may be blank or the browser stalled', EXIT_FAILED);
      director.recording = true;
      director.tl.cursorStart = { ...director.pos };
      await sleep(500); // a beat on the starting state before anything moves
      for (const [i, step] of shots.steps.entries()) {
        try { await director.run(step, i + 1, page.url()); } catch (e) {
          failure = { phase: 'step', index: i + 1, step, error: e };
          break;
        }
      }
      await sleep(600);
      director.recording = false;
      await cdp.send('Page.stopScreencast').catch(() => {});
      await sleep(100);
      if (!failure) await page.screenshot({ path: path.join(outDir, 'poster.png') });
    }
    if (failure) {
      const shot = path.join(outDir, `failed-${failure.phase}-${failure.index}.png`);
      await page.screenshot({ path: shot }).catch(() => {});
      let snapshot = '';
      try { snapshot = await ariaSnapshot(page, shots, 3000); } catch { /* ignore */ }
      const lines = snapshot.split('\n');
      const brief = lines.slice(0, 60).join('\n') + (lines.length > 60 ? `\n… ${lines.length - 60} more lines (run observe)` : '');
      const act = stepAction(failure.step)[0];
      throw new DemoError(
        `${failure.phase} ${failure.index} (${act} ${describeTarget(failure.step[act])}) failed: ${String(failure.error.message).split('\n')[0]}\n` +
        `page: ${page.url()}\nscreenshot: ${shot}\nwhat the page shows now (aria snapshot):\n${brief}`, EXIT_FAILED);
    }
  } catch (e) {
    if (!opts.keepWork) fs.rmSync(work, { recursive: true, force: true });
    throw e;
  } finally {
    await browser.close().catch(() => {});
  }

  const tl = director.tl;
  const lastEvent = Math.max(frames[frames.length - 1].t, ...tl.steps.map((s) => s.end));
  const duration = Math.round((lastEvent + 0.2) * 1000) / 1000;
  const video = path.join(outDir, 'demo.mp4');
  const camera = await compose(pw, g, shots, tl, frames, framesDir, duration, video);

  const probe = spawnSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,avg_frame_rate:format=duration', '-of', 'json', video], { encoding: 'utf8' });
  let probed = {};
  try {
    const j = JSON.parse(probe.stdout);
    probed = { width: j.streams[0].width, height: j.streams[0].height, seconds: Number(Number(j.format.duration).toFixed(2)) };
  } catch { /* leave empty */ }
  const deepest = Math.max(1, ...camera.shots.map((z) => z.z));
  const perPx = g.source[0] / deepest / g.content.w;
  if (perPx < RESOLUTION_FLOOR) {
    warnings.push(`the deepest zoom (${deepest}x) shows ${perPx.toFixed(2)} captured pixels per output pixel, so it looks soft. ` +
      `Raise "scale" to ${Math.ceil(((deepest * g.content.w * RESOLUTION_FLOOR) / g.vw) * 10) / 10} or give that zoom a lower "scale"`);
  }
  if (duration > TARGET_MAX_SECONDS) warnings.push(`the demo runs ${duration.toFixed(0)} s; reviewers rarely watch past ${TARGET_MAX_SECONDS}. Cut steps or split it`);
  const span = frames.length > 1 ? frames[frames.length - 1].t - frames[0].t : 0;
  const manifest = {
    video,
    poster: path.join(outDir, 'poster.png'),
    seconds: probed.seconds ?? duration,
    output: { width: g.W, height: g.H, fps: g.fps, framed: g.framed },
    capture: {
      device: g.device, viewport: { width: g.vw, height: g.vh }, scale: g.dpr,
      pixels: { width: g.source[0], height: g.source[1] }, touch: g.touch,
      frames: frames.length, average_fps: span > 0 ? Number((frames.length / span).toFixed(1)) : 0,
    },
    chapters: tl.marks.map((m) => ({ t: Number(m.t.toFixed(2)), label: m.label })),
    steps: tl.steps.map((s) => ({ ...s, start: Number(s.start.toFixed(2)), end: Number(s.end.toFixed(2)) })),
    zooms: camera.shots,
    interactions: { cursor_moves: tl.moves.length, clicks: tl.clicks.length, touches: tl.touches.length, keys: tl.keys.length, scrolls: tl.scrolls.length },
    warnings,
  };
  fs.writeFileSync(path.join(outDir, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
  if (opts.keepWork) fs.writeFileSync(path.join(work, 'timeline.json'), JSON.stringify({ frames, tl, camera }, null, 1));
  else fs.rmSync(work, { recursive: true, force: true });
  return manifest;
}

async function observe(target, opts, pw) {
  let shots = { url: target };
  let baseDir = process.cwd();
  if (fs.existsSync(target) && fs.statSync(target).isFile()) {
    shots = loadShots(target);
    baseDir = path.dirname(path.resolve(target));
  }
  if (opts.device) shots = { ...shots, device: opts.device };
  const g = resolveGeometry(shots, pw.devices);
  if (g.errors.length) throw new DemoError(g.errors.join('\n'), EXIT_INVALID);
  const browser = await launch(pw, { ...g, dpr: 1 });
  try {
    const context = await newContext(browser, shots, g, baseDir);
    const page = await context.newPage();
    const cdp = await context.newCDPSession(page);
    const d = new Director(page, cdp, shots, g);
    await page.goto(shots.url, { waitUntil: 'load', timeout: 30000 });
    const run = [...(shots.setup ?? []), ...(opts.steps ? shots.steps ?? [] : [])];
    for (const [i, step] of run.entries()) await d.run({ ...step, pause: 0 }, i + 1, page.url());
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
    const snapshot = await ariaSnapshot(page, shots, 10000);
    return { url: page.url(), title: await page.title(), viewport: { width: g.vw, height: g.vh }, touch: g.touch,
      hint: 'Targets: {"role": "button", "name": "Save"}, {"label": "Email"}, {"text": "..."}, {"testId": "..."} or any Playwright selector',
      snapshot };
  } finally {
    await browser.close().catch(() => {});
  }
}

// ── CLI ───────────────────────────────────────────────────────────────────

function loadShots(file) {
  let text;
  try { text = fs.readFileSync(file, 'utf8'); } catch { throw new DemoError(`shot list not found: ${file}`, EXIT_INVALID); }
  try { return JSON.parse(text); } catch (e) { throw new DemoError(`${file} is not valid JSON: ${e.message}`, EXIT_INVALID); }
}

function parseArgs(argv) {
  const [command, ...rest] = argv;
  const opts = { _: [] };
  for (let i = 0; i < rest.length; i++) {
    const a = rest[i];
    if (a === '--out') opts.out = rest[++i];
    else if (a === '--device') opts.device = rest[++i];
    else if (a === '--headed') opts.headed = true;
    else if (a === '--keep-work') opts.keepWork = true;
    else if (a === '--steps') opts.steps = true;
    else if (a === '-h' || a === '--help') opts.help = true;
    else if (a.startsWith('--')) throw new DemoError(`unknown option ${a}`, EXIT_INVALID);
    else opts._.push(a);
  }
  return { command, opts };
}

const USAGE = `usage:
  node record_demo.mjs check   SHOTS.json
  node record_demo.mjs observe URL|SHOTS.json [--device NAME] [--steps]
  node record_demo.mjs record  SHOTS.json --out DIR [--headed] [--keep-work]`;

async function main(argv) {
  const { command, opts } = parseArgs(argv);
  if (!command || opts.help || !['check', 'observe', 'record'].includes(command)) {
    process.stderr.write(`${USAGE}\n`);
    return command && !opts.help ? EXIT_INVALID : (opts.help ? EXIT_OK : EXIT_INVALID);
  }
  if (opts._.length !== 1) throw new DemoError(`${command} takes one argument\n${USAGE}`, EXIT_INVALID);
  const file = opts._[0];
  if (command === 'check') {
    const shots = loadShots(file);
    const pw = loadPlaywright({ required: false });
    const { errors, warnings, geometry: g } = validateShots(shots, pw?.devices ?? null);
    const est = Array.isArray(shots.steps) ? estimateSeconds(shots.steps) : 0;
    const report = { ok: errors.length === 0, errors, warnings, estimated_seconds: Number(est.toFixed(1)) };
    if (g && !g.errors?.length && !g.unresolved) {
      report.capture = { viewport: `${g.vw}x${g.vh}`, scale: g.dpr, pixels: `${g.source[0]}x${g.source[1]}`, touch: g.touch };
      report.output = { size: `${g.W}x${g.H}`, fps: g.fps, framed: g.framed, auto_zoom: g.autoZoom ? g.maxZoom : false };
    }
    if (!pw) report.warnings.push('playwright not found; record will need it (npm i -D playwright && npx playwright install chromium)');
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
    return errors.length ? EXIT_INVALID : EXIT_OK;
  }
  const pw = loadPlaywright();
  if (command === 'observe') {
    const r = await observe(file, opts, pw);
    process.stdout.write(`${JSON.stringify(r, null, 2)}\n`);
    return EXIT_OK;
  }
  if (!opts.out) throw new DemoError(`record needs --out DIR\n${USAGE}`, EXIT_INVALID);
  const shots = loadShots(file);
  const manifest = await record(shots, path.dirname(path.resolve(file)), path.resolve(opts.out), opts, pw);
  process.stdout.write(`${JSON.stringify(manifest, null, 2)}\n`);
  return EXIT_OK;
}

function estimateSeconds(steps) {
  let s = 1.1;
  for (const st of steps) {
    if (!isObj(st)) continue;
    const act = stepAction(st)[0];
    const pause = (st.pause ?? (['wait', 'waitFor', 'mark'].includes(act) ? 0 : STEP_PAUSE_MS)) / 1000;
    if (act === 'wait') s += st.wait / 1000;
    else if (act === 'type') s += 0.9 + (st.text?.length ?? 0) * ((st.delay ?? TYPE_DELAY_MS) / 1000) + pause;
    else if (act === 'zoom') s += st.zoom === 'out' ? ZOOM_OUT_S : (st.hold ?? EXPLICIT_HOLD_MS) / 1000;
    else if (act === 'scroll') s += (typeof st.scroll === 'number' ? Math.abs(st.scroll) / SCROLL_SPEED : 0.8) + 0.12 + pause;
    else if (act === 'goto') s += 1 + pause;
    else if (act && !['mark', 'waitFor'].includes(act)) s += 0.8 + pause;
  }
  return s;
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === new URL(import.meta.url).pathname;
if (isMain) {
  main(process.argv.slice(2)).then((code) => process.exit(code), (e) => {
    if (e instanceof DemoError) { process.stderr.write(`record_demo: ${e.message}\n`); process.exit(e.code); }
    process.stderr.write(`record_demo: ${e.stack || e}\n`);
    process.exit(EXIT_FAILED);
  });
}

export { validateShots, resolveGeometry, minJerk, keyLabel, loadPlaywright };
