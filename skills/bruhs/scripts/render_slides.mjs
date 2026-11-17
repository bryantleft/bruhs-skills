#!/usr/bin/env node
// render_slides.mjs — draw walkthrough slides as HTML in Chromium.
//
// walk_video.py calls this to draw each scene's slide (header, title card,
// points, code or diff, claims) as a 1920x1080 PNG. The browser lays out the
// text, so fit is measured, not estimated from average character widths;
// code is syntax-highlighted and shrinks to fit before it is refused.
//
// Usage (walk_video.py builds SPEC; not meant to be called by hand):
//   node render_slides.mjs probe
//   node render_slides.mjs render SPEC.json --out DIR [--measure-only]
//
// SPEC: {"pr": {...}, "scenes": [...], "layout": {...}, "colors": {...}}
// Prints {"scenes": [{"index", "slide", "errors"}]} as JSON.
// Exit codes: 0 ok (per-scene errors are in the JSON), 2 usage error,
// 3 Playwright or Chromium missing, 4 the browser failed.

import fs from 'node:fs';
import path from 'node:path';
import { loadPlaywright } from './record_demo.mjs';

const EXIT_INVALID = 2, EXIT_MISSING_TOOL = 3, EXIT_FAILED = 4;

// Code shrinks from the slide's code size to this before a scene is refused.
// 22 px on a 1080p frame is the smallest code that stays legible on a laptop
// screen at 1x playback (about 11 px at half-size, a common inline player).
const CODE_MIN_SIZE = 22;

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// ── Syntax highlighting: a small tokenizer, not a parser ─────────────────
// Comments, strings, numbers, keywords and calls cover what a reviewer scans
// for in a dozen lines. Unknown languages still get strings and numbers.

const KEYWORDS = new Set(`abstract as async await break case catch class const continue crate def default defer del
do elif else enum except export extends false final finally fn for from func go if impl implements import in
interface is lambda let loop match mod module mut new nil none None not null of or and package pass private
protected pub public raise readonly return self Self static struct super switch this throw throws trait true
True False try type typeof undefined unsafe use val var void where while with yield`.split(/\s+/));

const LINE_COMMENT = {
  hash: /^(py|rb|sh|bash|zsh|yaml|yml|toml|pl|r|ex|exs|nix|dockerfile|mk|makefile|conf|ini)$/,
  dash: /^(sql|lua|hs|elm)$/,
};

function commentStyle(file) {
  const base = path.basename(file || '').toLowerCase();
  const ext = base.includes('.') ? base.split('.').pop() : base;
  if (LINE_COMMENT.hash.test(ext)) return '#';
  if (LINE_COMMENT.dash.test(ext)) return '--';
  return '//';
}

function highlight(code, comment) {
  const lc = comment === '#' ? '#.*' : comment === '--' ? '--.*' : '\\/\\/.*';
  const re = new RegExp(
    `(${lc}|\\/\\*.*?\\*\\/)|("(?:[^"\\\\]|\\\\.)*"?|'(?:[^'\\\\]|\\\\.)*'?|\`(?:[^\`\\\\]|\\\\.)*\`?)` +
    '|(\\b\\d[\\d_]*(?:\\.\\d+)?(?:e[+-]?\\d+)?\\b|\\b0x[0-9a-f]+\\b)|([A-Za-z_$][\\w$]*)(?=\\s*\\()|([A-Za-z_$][\\w$]*)', 'gi');
  let out = '';
  let last = 0;
  for (const m of code.matchAll(re)) {
    out += esc(code.slice(last, m.index));
    const [tok, cmt, str, num, call, word] = m;
    if (cmt) out += `<span class="t-c">${esc(cmt)}</span>`;
    else if (str) out += `<span class="t-s">${esc(str)}</span>`;
    else if (num) out += `<span class="t-n">${esc(num)}</span>`;
    else if (call) out += KEYWORDS.has(call) ? `<span class="t-k">${esc(call)}</span>` : `<span class="t-f">${esc(call)}</span>`;
    else if (word && KEYWORDS.has(word)) out += `<span class="t-k">${esc(word)}</span>`;
    else if (word && /^[A-Z][A-Za-z0-9]*$/.test(word) && word.length > 1) out += `<span class="t-t">${esc(word)}</span>`;
    else out += esc(tok);
    last = m.index + tok.length;
  }
  return out + esc(code.slice(last));
}

// ── Slide HTML ────────────────────────────────────────────────────────────

const KIND_LABEL = { intent: 'WHY', change: 'WHAT CHANGED', implications: 'WHAT IT AFFECTS', validation: 'HOW WE KNOW' };
const STATUS_LABEL = { shown: 'SHOWN', intended: 'INTENDED', unchecked: 'NOT CHECKED' };

function css(L, C) {
  return `
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{width:${L.width}px;height:${L.height}px;overflow:hidden}
  body{background:#${C.bg};color:#${C.text};font-family:Inter,"SF Pro Display",-apple-system,"Helvetica Neue","Segoe UI","DejaVu Sans",sans-serif;
    -webkit-font-smoothing:antialiased;font-feature-settings:"cv11","ss01"}
  .glow{position:absolute;inset:0;background:radial-gradient(1200px 600px at 85% -10%,var(--accent-soft),transparent 70%)}
  .kind{position:absolute;left:${L.margin_x}px;top:${L.kind_y}px;font-size:26px;font-weight:700;letter-spacing:.12em;color:var(--accent)}
  .kind .pr{color:#${C.muted};font-weight:600}
  .heading{position:absolute;left:${L.margin_x}px;top:${L.heading_y}px;width:${L.content_w}px;font-size:${L.heading_size}px;font-weight:700;
    letter-spacing:-.02em;line-height:1.15;white-space:nowrap;overflow:hidden}
  .content{position:absolute;left:${L.margin_x}px;top:${L.content_top}px;width:${L.content_w}px;height:${L.content_h}px;overflow:hidden}
  .mono{font-family:"JetBrains Mono",Menlo,"SF Mono","DejaVu Sans Mono",monospace;font-variant-ligatures:none}
  .title{font-size:${L.title_size}px;font-weight:800;letter-spacing:-.03em;line-height:1.12;margin-top:40px}
  .meta{display:flex;gap:16px;margin-top:44px;flex-wrap:wrap}
  .chip{font-size:30px;padding:10px 20px;border-radius:999px;background:#1a1e26;color:#${C.muted};border:1px solid #262b35}
  .chip.add{color:#${C.add}} .chip.del{color:#${C.del}}
  .points{list-style:none;display:flex;flex-direction:column;gap:${L.point_gap}px}
  .points li{position:relative;padding-left:${L.point_indent}px;font-size:${L.point_size}px;line-height:1.26}
  .points li::before{content:"";position:absolute;left:6px;top:.5em;width:16px;height:16px;border-radius:50%;background:var(--accent)}
  .path{font-size:26px;color:#${C.muted};margin-bottom:16px;height:34px}
  .code{background:#141821;border:1px solid #232835;border-radius:16px;padding:20px 0;overflow:hidden;height:${L.content_h - 50}px}
  .code .row{display:flex;white-space:pre;line-height:1.3;padding:0 28px 0 0}
  .code .gut{flex:none;width:4.2ch;text-align:right;padding-right:1.4ch;color:#4a5263;user-select:none}
  .code .sign{flex:none;width:2ch;color:#4a5263}
  .row.add{background:rgba(158,206,106,.13)} .row.add .sign{color:#${C.add}}
  .row.del{background:rgba(247,118,142,.13)} .row.del .sign{color:#${C.del}}
  .row.hunk{color:#${C.hunk}} .row.hunk .sign{color:#${C.hunk}}
  .t-c{color:#6b7385;font-style:italic} .t-s{color:#9ece6a} .t-n{color:#ff9e64} .t-k{color:#bb9af7}
  .t-f{color:#7aa2f7} .t-t{color:#2ac3de}
  .claims{display:flex;flex-direction:column;gap:${L.claim_gap}px}
  .claim{display:grid;grid-template-columns:${L.claim_tag_w}px 1fr;align-items:start}
  .pill{justify-self:start;font-size:24px;font-weight:800;letter-spacing:.08em;padding:9px 16px;border-radius:10px;margin-top:4px}
  .pill.shown{color:#${C.shown};background:rgba(158,206,106,.14)}
  .pill.intended{color:#${C.intended};background:rgba(224,175,104,.14)}
  .pill.unchecked{color:#${C.unchecked};background:rgba(139,147,161,.14)}
  .claim .text{font-size:${L.claim_size}px;line-height:1.25;font-weight:600}
  .claim .receipt{font-size:${L.receipt_size}px;color:#${C.muted};margin-top:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  `;
}

function visualHtml(scene, pr) {
  const v = scene.visual;
  switch (v.type) {
    case 'title': {
      const meta = [];
      if (pr.base && pr.head) meta.push(`<span class="chip mono">${esc(pr.base)} ← ${esc(pr.head)}</span>`);
      if (Number.isInteger(pr.additions) && Number.isInteger(pr.deletions)) {
        meta.push(`<span class="chip mono add">+${pr.additions}</span><span class="chip mono del">−${pr.deletions}</span>`);
      }
      if (Number.isInteger(pr.files)) meta.push(`<span class="chip">${pr.files} files</span>`);
      return `<div class="title" id="title">${esc(pr.title)}</div><div class="meta">${meta.join('')}</div>`;
    }
    case 'points':
      return `<ul class="points" id="fit">${v.items.map((i) => `<li>${esc(i)}</li>`).join('')}</ul>`;
    case 'code': case 'diff': {
      const comment = commentStyle(v.path);
      const lines = v.text.replace(/\n+$/, '').split('\n').map((l) => l.replace(/\t/g, '    ').replace(/\s+$/, ''));
      let n = Number.isInteger(v.start_line) ? v.start_line : null;
      const rows = lines.map((line) => {
        if (v.type === 'diff') {
          if (line.startsWith('@@')) return `<div class="row hunk"><span class="sign"></span><span>${esc(line)}</span></div>`;
          const sign = line[0] === '+' || line[0] === '-' || line[0] === ' ' ? line[0] : ' ';
          const body = sign === line[0] ? line.slice(1) : line;
          const cls = sign === '+' ? 'add' : sign === '-' ? 'del' : '';
          return `<div class="row ${cls}"><span class="sign">${sign === ' ' ? '' : esc(sign)}</span><span>${highlight(body, comment)}</span></div>`;
        }
        const gut = n === null ? '' : `<span class="gut">${n++}</span>`;
        return `<div class="row">${gut || '<span class="sign"></span>'}<span>${highlight(line, comment)}</span></div>`;
      }).join('');
      const label = v.path ? `${esc(v.path)}${v.start_line ? `:${v.start_line}` : ''}` : '';
      return `<div class="path mono">${label}</div><div class="code mono" id="code">${rows}</div>`;
    }
    case 'claims':
      return `<div class="claims" id="fit">${scene.claims.map((c) => `<div class="claim"><span class="pill ${c.status}">${STATUS_LABEL[c.status]}</span>` +
        `<div><div class="text">${esc(c.text)}</div>${c.receipt ? `<div class="receipt mono">${esc(String(c.receipt).split(/\s+/).join(' '))}</div>` : ''}</div></div>`).join('')}</div>`;
    default:
      return ''; // image and video are composited by ffmpeg into the empty content box
  }
}

function slideHtml(scene, pr, L, C) {
  const accent = C[scene.kind];
  const prLabel = pr.number ? `<span class="pr">PR #${esc(pr.number)}  ·  </span>` : '';
  return `<!doctype html><html><head><meta charset="utf-8"><style>${css(L, C)}
  :root{--accent:#${accent};--accent-soft:#${accent}22}</style></head><body>
  <div class="glow"></div>
  <div class="kind">${prLabel}${KIND_LABEL[scene.kind]}</div>
  <div class="heading" id="heading">${esc(scene.heading)}</div>
  <div class="content" id="content">${visualHtml(scene, pr)}</div></body></html>`;
}

// Runs in the page: shrink code to fit, then report what still overflows.
function measure({ codeSize, codeMin, titleMaxLines }) {
  const errors = [];
  const heading = document.getElementById('heading');
  if (heading.scrollWidth > heading.clientWidth + 1) {
    errors.push(`heading is ${heading.scrollWidth - heading.clientWidth}px wider than one line holds. Shorten it`);
  }
  const title = document.getElementById('title');
  if (title) {
    const lh = parseFloat(getComputedStyle(title).lineHeight);
    const lines = Math.round(title.getBoundingClientRect().height / lh);
    if (lines > titleMaxLines) errors.push(`pr.title wraps to ${lines} lines; the title card holds ${titleMaxLines}`);
  }
  const code = document.getElementById('code');
  let codeFontPx = null;
  if (code) {
    const rows = [...code.querySelectorAll('.row')];
    const fits = () => code.scrollHeight <= code.clientHeight + 1 && rows.every((r) => r.scrollWidth <= code.clientWidth);
    let size = codeSize;
    code.style.fontSize = `${size}px`;
    while (!fits() && size > codeMin) { size -= 1; code.style.fontSize = `${size}px`; }
    codeFontPx = size;
    if (!fits()) {
      const rowH = rows[0].getBoundingClientRect().height;
      const pad = parseFloat(getComputedStyle(code).paddingTop) * 2;
      const holds = Math.floor((code.clientHeight - pad) / rowH);
      if (code.scrollHeight > code.clientHeight + 1) {
        errors.push(`${rows.length} lines of code; the slide holds ${holds} at the smallest code size. Trim to the lines the narration talks about`);
      }
      const probe = document.createElement('span');
      probe.textContent = 'x'.repeat(100);
      probe.style.whiteSpace = 'pre';
      code.appendChild(probe);
      const ch = probe.getBoundingClientRect().width / 100;
      probe.remove();
      const widest = rows.reduce((a, r) => Math.max(a, r.scrollWidth), 0);
      if (widest > code.clientWidth) {
        const gutter = rows[0].firstElementChild.getBoundingClientRect().width + 28;
        const cols = Math.floor((code.clientWidth - gutter) / ch);
        const used = Math.round((widest - gutter) / ch);
        errors.push(`a code line is ${used} columns; the slide holds ${cols} at the smallest code size. Reflow or cut that line`);
      }
    }
  }
  const fit = document.getElementById('fit');
  if (fit) {
    const content = document.getElementById('content');
    const need = Math.ceil(fit.scrollHeight);
    if (need > content.clientHeight) {
      const what = fit.classList.contains('claims') ? 'claims' : 'points';
      const advice = what === 'claims' ? 'Merge or shorten claims; the transcript keeps the full receipts' : 'Use fewer or shorter items';
      errors.push(`the ${what} need ${need}px; the slide holds ${content.clientHeight}px. ${advice}`);
    }
  }
  return { errors, codeFontPx };
}

async function render(spec, outDir, measureOnly) {
  const pw = loadPlaywright();
  let browser;
  try {
    browser = await pw.chromium.launch({ headless: true, ...(process.env.BRUHS_CHROMIUM ? { executablePath: process.env.BRUHS_CHROMIUM } : {}) });
  } catch (e) {
    const err = new Error(`chromium could not start: ${String(e.message).split('\n')[0]}. Run: npx playwright install chromium`);
    err.code = EXIT_MISSING_TOOL;
    throw err;
  }
  const L = spec.layout, C = spec.colors;
  const results = [];
  try {
    const page = await browser.newPage({ viewport: { width: L.width, height: L.height }, deviceScaleFactor: 1 });
    for (const [i, scene] of spec.scenes.entries()) {
      const index = i + 1;
      const filled = ['image', 'video'].includes(scene.visual.type) && scene.visual.fill === true;
      if (filled) { results.push({ index, slide: null, errors: [] }); continue; }
      await page.setContent(slideHtml(scene, spec.pr ?? {}, L, C), { waitUntil: 'load' });
      await page.evaluate(() => document.fonts.ready);
      const m = await page.evaluate(measure, { codeSize: L.code_size, codeMin: CODE_MIN_SIZE, titleMaxLines: L.title_max_lines });
      let slide = null;
      if (!measureOnly && !m.errors.length) {
        slide = path.join(outDir, `slide${String(index).padStart(2, '0')}.png`);
        await page.screenshot({ path: slide });
      }
      results.push({ index, slide, errors: m.errors, code_font_px: m.codeFontPx });
    }
  } finally {
    await browser.close().catch(() => {});
  }
  return results;
}

async function main(argv) {
  const [command, ...rest] = argv;
  if (command === 'probe') {
    const pw = loadPlaywright();
    const b = await pw.chromium.launch({ headless: true, ...(process.env.BRUHS_CHROMIUM ? { executablePath: process.env.BRUHS_CHROMIUM } : {}) });
    await b.close();
    process.stdout.write('{"ok": true}\n');
    return 0;
  }
  if (command !== 'render') { process.stderr.write('usage: render_slides.mjs probe | render SPEC.json --out DIR [--measure-only]\n'); return EXIT_INVALID; }
  const file = rest.find((a) => !a.startsWith('--') && rest[rest.indexOf(a) - 1] !== '--out');
  const outIdx = rest.indexOf('--out');
  const measureOnly = rest.includes('--measure-only');
  if (!file || (!measureOnly && outIdx < 0)) { process.stderr.write('render needs SPEC.json and --out DIR\n'); return EXIT_INVALID; }
  const spec = JSON.parse(fs.readFileSync(file, 'utf8'));
  const outDir = outIdx >= 0 ? rest[outIdx + 1] : null;
  if (outDir) fs.mkdirSync(outDir, { recursive: true });
  const scenes = await render(spec, outDir, measureOnly);
  process.stdout.write(`${JSON.stringify({ scenes }, null, 2)}\n`);
  return 0;
}

main(process.argv.slice(2)).then((code) => process.exit(code), (e) => {
  process.stderr.write(`render_slides: ${e.message}\n`);
  process.exit(e.code === EXIT_MISSING_TOOL || e.code === 3 ? EXIT_MISSING_TOOL : EXIT_FAILED);
});
