#!/usr/bin/env node
/*
 * JobCopilot frontend build (P1-6).
 *
 * The extracted modules are classic scripts that share one global lexical scope
 * (app.js defines `state`, `els`, helpers; the modules read them). ESM bundling
 * would give each file its own scope and break that, so we CONCATENATE the
 * sources in load order and minify the result as a single classic script — same
 * semantics as the separate <script> tags, but one minified, content-hashed file.
 *
 * Output: js/app.bundle.<hash>.js (+ .map). index.html is rewritten to load it,
 * between the <!-- BUILD:JS --> markers. Run: `npm run build` (in frontend/).
 */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const esbuild = require('esbuild');

const ROOT = __dirname;
const JS_DIR = path.join(ROOT, 'js');

// Load order matters: error reporter first (catch early errors), then app.js
// (defines the shared globals), then feature modules that read those globals.
const SOURCES = [
  'js/error-reporter.js',
  'js/app.js',
  'js/modules/command-palette.js',
  'js/modules/interview-studio.js',
  'js/modules/knowledge-vault.js',
  'js/modules/negotiation.js',
  'js/modules/inbound-email.js',
  'js/modules/reverse-interview.js',
  'js/modules/pipeline-actions.js',
  'js/modules/pwa-install.js',
];

async function main() {
  const sourceHashes = {};
  const combined = SOURCES
    .map((rel) => {
      const p = path.join(ROOT, rel);
      if (!fs.existsSync(p)) throw new Error(`Missing source: ${rel}`);
      const text = fs.readFileSync(p, 'utf8');
      sourceHashes[rel] = crypto.createHash('sha256').update(text).digest('hex');
      return `/* ==== ${rel} ==== */\n` + text;
    })
    .join('\n;\n');

  const result = await esbuild.transform(combined, {
    minify: true,
    sourcemap: true,
    sourcefile: 'app.bundle.src.js',
    legalComments: 'none',
    target: 'es2019',
  });

  const hash = crypto.createHash('sha256').update(result.code).digest('hex').slice(0, 12);
  const bundleName = `app.bundle.${hash}.js`;

  // Remove any previously-built bundles so only the current one remains.
  for (const f of fs.readdirSync(JS_DIR)) {
    if (/^app\.bundle\.[0-9a-f]+\.js(\.map)?$/.test(f)) fs.unlinkSync(path.join(JS_DIR, f));
  }

  fs.writeFileSync(path.join(JS_DIR, bundleName), result.code + `\n//# sourceMappingURL=${bundleName}.map\n`);
  fs.writeFileSync(path.join(JS_DIR, `${bundleName}.map`), result.map);

  // Rewrite the marked block in index.html to point at the new bundle.
  const indexPath = path.join(ROOT, 'index.html');
  let html = fs.readFileSync(indexPath, 'utf8');
  const block = `<!-- BUILD:JS -->\n  <script src="/js/${bundleName}"></script>\n  <!-- /BUILD:JS -->`;
  const markerRe = /<!-- BUILD:JS -->[\s\S]*?<!-- \/BUILD:JS -->/;
  if (!markerRe.test(html)) throw new Error('index.html is missing the <!-- BUILD:JS --> ... <!-- /BUILD:JS --> markers');
  html = html.replace(markerRe, block);
  fs.writeFileSync(indexPath, html);

  // Deterministic freshness manifest (source SHA-256s, platform-independent).
  // CI rebuilds and diffs this to catch a source edited without rebuilding the
  // bundle — without depending on esbuild's byte output matching across OSes.
  fs.writeFileSync(
    path.join(JS_DIR, 'build-manifest.json'),
    JSON.stringify({ sources: sourceHashes }, null, 2) + '\n'
  );

  console.log(`Built js/${bundleName} (${(result.code.length / 1024).toFixed(1)} KB minified) and updated index.html`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
