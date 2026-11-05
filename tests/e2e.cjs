// Test de bout en bout dans Chromium (Playwright).
//
//   python3 tests/generer_pdf_test.py /tmp/pdf-test
//   node tests/e2e.cjs /tmp/pdf-test /tmp/sortie-test
//
// Vérifie : glisser-déposer d'un fichier, détection des zones (attendu.json),
// message douane, téléchargement (nom + PDF), bouton Imprimer (nouvel onglet),
// ajustement du cadre à la souris, et l'absence d'erreur/avertissement console.
const { chromium, devices } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const PDF_DIR = path.resolve(process.argv[2] || path.join(__dirname, 'pdf'));
const OUT_DIR = path.resolve(process.argv[3] || path.join(__dirname, 'sortie'));
const PORT = 8765 + Math.floor(Math.random() * 1000);
const expected = JSON.parse(fs.readFileSync(path.join(PDF_DIR, 'attendu.json'), 'utf8'));
fs.mkdirSync(OUT_DIR, { recursive: true });

let failures = 0;
const ok = (cond, msg) => { console.log(`${cond ? '  ✔' : '  ✘'} ${msg}`); if (!cond) failures++; };

async function main() {
  const server = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1', '--directory', ROOT], { stdio: 'ignore' });
  await new Promise((r) => setTimeout(r, 800));
  const proxy = process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY, bypass: '127.0.0.1,localhost' } : undefined;
  // Chromium complet (nouveau mode headless) : il possède le lecteur PDF intégré, contrairement à « headless shell ».
  const browser = await chromium.launch({ proxy, channel: process.env.PW_CHANNEL || 'chromium' });
  const consoleIssues = [];
  try {
    const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    const watch = (p) => {
      p.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') consoleIssues.push(`[${m.type()}] ${m.text()}`); });
      p.on('pageerror', (e) => consoleIssues.push(`[pageerror] ${e.message}`));
    };
    watch(page);
    const external = [];
    page.on('request', (r) => { const u = new URL(r.url()); if (!['127.0.0.1', 'cdn.jsdelivr.net'].includes(u.hostname) && !r.url().startsWith('blob:') && !r.url().startsWith('data:')) external.push(r.url()); });

    await page.goto(`http://127.0.0.1:${PORT}/index.html`);
    await page.evaluate(() => window.MunbynApp.libsReady);
    console.log('Page chargée, librairies prêtes.');

    // 1) Glisser-déposer d'un fichier
    const first = 'colissimo_france.pdf';
    const b64 = fs.readFileSync(path.join(PDF_DIR, first)).toString('base64');
    await page.evaluate(({ b64, name }) => {
      const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const dt = new DataTransfer();
      dt.items.add(new File([bin], name, { type: 'application/pdf' }));
      const dz = document.getElementById('dropzone');
      for (const type of ['dragenter', 'dragover', 'drop']) {
        dz.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt }));
      }
    }, { b64, name: first });
    await page.waitForFunction(() => window.MunbynApp.state.files[0]?.status === 'ready', null, { timeout: 30000 });
    ok(true, `fichier glissé-déposé et analysé (${first})`);

    // 2) Les autres fichiers via le bouton (input file)
    const others = Object.keys(expected).filter((n) => n !== first);
    await page.setInputFiles('#file-input', others.map((n) => path.join(PDF_DIR, n)));
    await page.waitForFunction((n) => {
      const f = window.MunbynApp.state.files;
      return f.length === n && f.every((x) => x.status === 'ready' || x.status === 'error');
    }, others.length + 1, { timeout: 60000 });

    // 3) Détection des zones
    console.log('Détection :');
    const names = await page.evaluate(() => window.MunbynApp.state.files.map((f) => f.name));
    for (const [fi, name] of names.entries()) {
      const exp = expected[name];
      const info = await page.evaluate((fi) => {
        const f = window.MunbynApp.state.files[fi];
        return { status: f.status, hasCustoms: f.hasCustoms, carriers: f.carriers, n: f.pages.length,
          pages: f.pages.map((p, pi) => ({ source: p.auto.source, preset: p.auto.presetId, box: window.MunbynApp.visualBox(fi, pi), checked: p.checked })) };
      }, fi);
      ok(info.status === 'ready', `${name} : prêt (${info.n} page(s), transporteurs : ${info.carriers.join(', ') || '—'})`);
      ok(info.hasCustoms === exp.customs, `${name} : douane = ${info.hasCustoms}`);
      ok(info.pages.map((p) => p.checked).join() === info.pages.map((_, i) => i === 0).join(), `${name} : seule la page 1 est cochée par défaut`);
      for (const [pi, e] of Object.entries(exp.boxes)) {
        const got = info.pages[pi];
        const tol = e.loose ? 20 : 6;
        const diff = got.box.map((v, k) => Math.abs(v - e.box[k]));
        const fmt = (b) => b.map((v) => v.toFixed(1)).join(', ');
        ok(got.source === e.source && Math.max(...diff) <= tol,
          `${name} p${+pi + 1} : ${got.source}${got.preset ? ' (' + got.preset + ')' : ''} [${fmt(got.box)}] attendu ${e.source} [${fmt(e.box)}] (écart max ${Math.max(...diff).toFixed(1)} pt)`);
        if (e.source === 'rect') {
          const contains = got.box[0] <= e.box[0] + 1.5 && got.box[1] <= e.box[1] + 1.5 && got.box[2] >= e.box[2] - 1.5 && got.box[3] >= e.box[3] - 1.5;
          ok(contains, `${name} p${+pi + 1} : la zone contient tout le cadre plein (sans le cadre pointillé)`);
        }
      }
      const warn = await page.locator(`article.card:nth-of-type(${fi + 1}) .alert.warn`).count();
      ok((warn > 0) === exp.customs, `${name} : message douane ${exp.customs ? 'affiché' : 'absent'}`);
    }
    const customsText = await page.locator('.alert.warn strong').first().textContent();
    ok(customsText === 'Envoi hors UE : imprime aussi les papiers de douane en A4', 'texte exact du message douane');
    const reminder = await page.locator('.reminder').textContent();
    ok(reminder.includes('Imprimer en 4×6, échelle 100 % (pas "ajuster à la page")'), 'rappel d\'impression affiché');

    // 4) Téléchargement (1er fichier)
    const card1 = page.locator('article.card').first();
    const [dl] = await Promise.all([page.waitForEvent('download'), card1.getByRole('button', { name: 'Télécharger' }).click()]);
    const dlPath = path.join(OUT_DIR, dl.suggestedFilename());
    await dl.saveAs(dlPath);
    ok(dl.suggestedFilename() === 'etiquette_colissimo_france_MUNBYN_4x6.pdf', `nom du fichier téléchargé : ${dl.suggestedFilename()}`);

    // Téléchargement de chaque fichier (page 1 + pages de douane cochées pour l'international)
    for (const [fi, name] of names.entries()) {
      if (fi === 0) continue;
      const card = page.locator('article.card').nth(fi);
      if (name.startsWith('fedex')) {
        await card.locator('.thumb-check input').nth(1).check();
        await card.locator('.thumb-check input').nth(2).check();
      }
      const [d] = await Promise.all([page.waitForEvent('download'), card.getByRole('button', { name: 'Télécharger' }).click()]);
      await d.saveAs(path.join(OUT_DIR, d.suggestedFilename()));
    }
    const [dlAll] = await Promise.all([page.waitForEvent('download'), page.locator('#all-dl').click()]);
    await dlAll.saveAs(path.join(OUT_DIR, dlAll.suggestedFilename()));
    ok(true, `« Tout télécharger » : ${dlAll.suggestedFilename()}`);

    // 5) Imprimer : ouvre le PDF généré dans un nouvel onglet
    const popupPromise = context.waitForEvent('page');
    await card1.getByRole('button', { name: 'Imprimer' }).click();
    const popup = await popupPromise;
    watch(popup);
    const popupDownload = popup.waitForEvent('download', { timeout: 15000 }).catch(() => null);
    await popup.waitForURL(/^blob:/, { timeout: 15000 }).catch(() => {});
    if (popup.url().startsWith('blob:')) {
      await popup.waitForTimeout(3000);   // laisse le lecteur PDF de Chrome s'afficher
      const viewer = popup.frames().some((fr) => fr.url().startsWith('chrome-extension://'));
      ok(true, `« Imprimer » ouvre un nouvel onglet sur le PDF généré (${popup.url().slice(0, 30)}…, lecteur PDF ${viewer ? 'chargé' : 'non détecté'})`);
      await popup.screenshot({ path: path.join(OUT_DIR, 'onglet_imprimer.png') }).catch(() => {});
    } else {
      const d = await popupDownload;   // navigateur sans lecteur PDF : l'onglet télécharge le PDF
      ok(!!d, `« Imprimer » ouvre un nouvel onglet qui reçoit le PDF généré${d ? ' (' + d.suggestedFilename() + ')' : ''}`);
    }
    await popup.close();

    // 6) Ajustement du cadre à la souris (poignée bas-droite) puis retour à la détection auto
    await card1.scrollIntoViewIfNeeded();
    const before = await page.evaluate(() => ({ ...window.MunbynApp.state.files[0].pages[0].crop }));
    const handle = card1.locator('.h[data-h="se"]');
    const hb = await handle.boundingBox();
    await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2);
    await page.mouse.down();
    await page.mouse.move(hb.x - 40, hb.y - 60, { steps: 8 });
    await page.mouse.up();
    const after = await page.evaluate(() => {
      const p = window.MunbynApp.state.files[0].pages[0];
      return { crop: { ...p.crop }, choice: p.choice };
    });
    ok(after.choice === 'custom' && after.crop.x1 < before.x1 - 10 && after.crop.y0 > before.y0 + 10,
      `poignée déplacée à la souris : x1 ${before.x1.toFixed(1)}→${after.crop.x1.toFixed(1)}, y0 ${before.y0.toFixed(1)}→${after.crop.y0.toFixed(1)}`);
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(OUT_DIR, 'ecran_ajuste.png'), fullPage: false });
    await card1.getByRole('button', { name: 'Détection auto' }).click();
    const restored = await page.evaluate(() => window.MunbynApp.state.files[0].pages[0].choice);
    ok(restored === 'auto', 'bouton « Détection auto » restaure la zone détectée');
    await page.waitForTimeout(600);

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(OUT_DIR, 'ecran_bureau.png'), fullPage: true });
    // Capture de la carte « FedEx international » sélectionnée sur la page CN23
    const intlIdx = names.findIndex((n) => n.startsWith('fedex'));
    const intl = page.locator('article.card').nth(intlIdx);
    await intl.locator('.thumb-view').nth(1).click();
    await page.waitForTimeout(800);
    await intl.screenshot({ path: path.join(OUT_DIR, 'carte_international_cn23.png') });

    // 7) Mobile
    const mctx = await browser.newContext({ ...devices['iPhone 13'] });
    const m = await mctx.newPage();
    watch(m);
    await m.goto(`http://127.0.0.1:${PORT}/index.html`);
    await m.evaluate(() => window.MunbynApp.libsReady);
    await m.setInputFiles('#file-input', [path.join(PDF_DIR, 'ups.pdf')]);
    await m.waitForFunction(() => window.MunbynApp.state.files[0]?.status === 'ready', null, { timeout: 30000 });
    await m.waitForTimeout(800);
    await m.screenshot({ path: path.join(OUT_DIR, 'ecran_mobile.png'), fullPage: true });
    // En émulation mobile, innerWidth s'élargit avec le contenu : on compare à la largeur de l'écran (clientWidth).
    const overflow = await m.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    ok(overflow <= 1, `mobile : pas de défilement horizontal (débord ${overflow}px)`);
    await mctx.close();

    // 8) Fichier qui n'est pas un PDF : message d'erreur clair, pas de plantage
    await page.evaluate(() => {
      const dt = new DataTransfer();
      dt.items.add(new File(['ceci n\'est pas un PDF'], 'notes.txt', { type: 'text/plain' }));
      document.getElementById('dropzone').dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt }));
    });
    await page.waitForFunction(() => window.MunbynApp.state.files.some((f) => f.name === 'notes.txt' && f.status === 'error'));
    const errText = await page.locator('article.card:last-of-type .alert.error').textContent();
    ok(errText.includes('pas un PDF'), `fichier non-PDF refusé proprement (« ${errText} »)`);

    ok(external.length === 0, `aucune requête hors CDN des librairies${external.length ? ' : ' + external.join(', ') : ''}`);
  } finally {
    ok(consoleIssues.length === 0, `console sans erreur ni avertissement${consoleIssues.length ? ' :\n      ' + consoleIssues.join('\n      ') : ''}`);
    await browser.close();
    server.kill();
  }
  console.log(failures ? `\n${failures} échec(s)` : '\nTous les tests e2e sont passés.');
  process.exit(failures ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(2); });
