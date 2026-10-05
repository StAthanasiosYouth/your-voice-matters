// Renders video/scene.html to MP4, frame by frame.
//
//   node render.mjs                     both formats -> ../videos/<name>-vN.mp4 (next free N)
//   node render.mjs --version 7         force a version number (still never overwrites)
//   node render.mjs --format portrait   one format
//   node render.mjs --still 23.5        PNG of one moment (both formats)
//   node render.mjs --serve             preview server at http://localhost:4173/video/scene.html
//
// Needs Chrome or Edge installed, and ffmpeg on PATH. Run `python music.py` first.

import { createServer } from 'node:http';
import { readFile, writeFile, mkdir, stat, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { extname, join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer-core';
import QRCode from 'qrcode';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const outDir = join(root, 'videos');
const timeline = JSON.parse(await readFile(join(here, 'timeline.json'), 'utf8'));

const args = process.argv.slice(2);
const flag = name => args.includes(name);
const option = name => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : undefined;
};

const FORMATS = {
  landscape: { width: 1920, height: 1080, name: 'your-voice-matters-16x9' },
  portrait: { width: 1080, height: 1920, name: 'your-voice-matters-9x16' }
};

const MIME = {
  '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.js': 'text/javascript',
  '.mjs': 'text/javascript', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg'
};


/* ---------- QR code for the call to action ---------- */

await writeFile(
  join(here, 'qr.svg'),
  await QRCode.toString(timeline.url, {
    type: 'svg',
    margin: 0,
    errorCorrectionLevel: 'M',
    color: { dark: '#06172a', light: '#ffffff' }
  })
);


/* ---------- static server (project root) ---------- */

const server = createServer(async (req, res) => {
  try {
    const path = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    const file = resolve(root, '.' + path);
    if (!file.startsWith(root)) throw new Error('outside root');
    const body = await readFile(file);
    res.writeHead(200, { 'Content-Type': MIME[extname(file)] || 'application/octet-stream' });
    res.end(body);
  } catch {
    res.writeHead(404);
    res.end();
  }
});

const port = Number(option('--port') || 4173);
await new Promise(ok => server.listen(port, '127.0.0.1', ok));
const base = `http://127.0.0.1:${port}/video/scene.html`;

if (flag('--serve')) {
  console.log(`Preview: ${base}?format=landscape&t=0   (add ?format=portrait, change t)`);
  await new Promise(() => {});
}


/* ---------- browser ---------- */

const chromePath = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome'
].find(p => p && existsSync(p));

if (!chromePath) throw new Error('Chrome/Edge not found; set CHROME_PATH');

const browser = await puppeteer.launch({
  executablePath: chromePath,
  headless: true,
  args: ['--hide-scrollbars', '--force-color-profile=srgb', '--disable-lcd-text']
});

async function openScene(format) {
  const { width, height } = FORMATS[format];
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1 });
  page.on('pageerror', err => console.error('[page]', err.message));
  await page.goto(`${base}?format=${format}`, { waitUntil: 'networkidle0' });
  await page.evaluate(() => window.sceneReady);
  return page;
}

const selected = option('--format') ? [option('--format')] : Object.keys(FORMATS);
await mkdir(outDir, { recursive: true });


/* ---------- stills ---------- */

if (option('--still') !== undefined) {
  const times = option('--still').split(',').map(Number);
  const stillDir = option('--out') || here;
  await mkdir(stillDir, { recursive: true });
  for (const format of selected) {
    const page = await openScene(format);
    for (const t of times) {
      await page.evaluate(time => window.renderAt(time), t);
      const file = join(stillDir, `still-${format}-${t}.png`);
      await page.screenshot({ path: file });
      console.log('wrote', file);
    }
    await page.close();
  }
  await browser.close();
  server.close();
  process.exit(0);
}


/* ---------- video ---------- */

const music = join(here, 'music.wav');
const hasMusic = existsSync(music);
if (!hasMusic) console.warn('music.wav not found, rendering silent video (run `python music.py`)');

const fps = timeline.fps;
const total = Math.round(timeline.duration * fps);

/* every render is a new version (name-vN.mp4); earlier renders are never overwritten */
const existing = (await readdir(outDir)).map(f => /-v(\d+)\.mp4$/.exec(f)).filter(Boolean).map(m => Number(m[1]));
const version = Number(option('--version')) || Math.max(0, ...existing) + 1;
console.log(`rendering version v${version}`);

for (const format of selected) {

  const page = await openScene(format);
  const out = join(outDir, `${FORMATS[format].name}-v${version}.mp4`);
  if (existsSync(out)) throw new Error(`${out} already exists; refusing to overwrite`);

  const ffmpeg = spawn('ffmpeg', [
    '-y', '-loglevel', 'error',
    '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-',
    ...(hasMusic ? ['-i', music] : []),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p',
    '-profile:v', 'high', '-tune', 'animation',
    ...(hasMusic ? ['-c:a', 'aac', '-b:a', '192k', '-shortest'] : []),
    '-movflags', '+faststart',
    out
  ], { stdio: ['pipe', 'inherit', 'inherit'] });

  const done = new Promise((ok, fail) => ffmpeg.on('close', code => code ? fail(new Error('ffmpeg ' + code)) : ok()));
  const started = Date.now();

  for (let frame = 0; frame < total; frame++) {
    await page.evaluate(time => window.renderAt(time), frame / fps);
    const png = await page.screenshot({ type: 'png', optimizeForSpeed: true });
    if (!ffmpeg.stdin.write(png)) await new Promise(ok => ffmpeg.stdin.once('drain', ok));
    if (frame % 150 === 0) {
      const secs = ((Date.now() - started) / 1000).toFixed(0);
      console.log(`${format}: frame ${frame}/${total} (${secs}s)`);
    }
  }

  ffmpeg.stdin.end();
  await done;
  await page.close();

  const { size } = await stat(out);
  console.log(`wrote ${out} (${(size / 1e6).toFixed(1)} MB)`);
}

await browser.close();
server.close();
