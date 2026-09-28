// Скриншоты страниц для README и PR + автоматическая проверка доступности (axe-core).
//
//   npm run build && npx vite preview --port 4173 &
//   npm run screenshots                       # все страницы → ../docs/screenshots
//   npm run screenshots -- --only home,search --axe
//
// Нужен Chromium для Playwright: `npx playwright install chromium`
// (или путь к готовому браузеру в переменной CHROMIUM_PATH).
// SCREENSHOT_PROXY_FONTS=1 — загружать Google Fonts через Node (для песочниц с прокси).
import { AxeBuilder } from '@axe-core/playwright';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from 'playwright';

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};
const base = option('base', 'http://localhost:4173/');
const outDir = resolve(option('out', '../docs/screenshots'));
const only = option('only', '').split(',').filter(Boolean);
const runAxe = args.includes('--axe');

const DESKTOP = { width: 1360, height: 900 };
const MOBILE = { width: 390, height: 844 };

/** name, hash-маршрут, тема, размер, снимок всей страницы, действия перед снимком. */
const SHOTS = [
  { name: 'home', route: '/', theme: 'light', size: DESKTOP, full: true },
  { name: 'home-dark', route: '/', theme: 'dark', size: DESKTOP, full: false },
  { name: 'home-mobile', route: '/', theme: 'light', size: MOBILE, full: false },
  { name: 'search', route: '/search?q=книг', theme: 'light', size: DESKTOP, full: false },
  {
    name: 'search-filters',
    route: '/search?phen=case&sub=gent',
    theme: 'dark',
    size: DESKTOP,
    full: false,
  },
  {
    name: 'search-kwic',
    route: '/search?phen=classifier&mode=kwic&sort=keyword',
    theme: 'light',
    size: DESKTOP,
    full: false,
  },
  { name: 'search-mobile', route: '/search?q=чай', theme: 'light', size: MOBILE, full: false },
  { name: 'pair', route: '/pair/example-011', theme: 'light', size: DESKTOP, full: true },
  { name: 'pair-dark', route: '/pair/example-018', theme: 'dark', size: DESKTOP, full: false },
  { name: 'stats', route: '/stats', theme: 'light', size: DESKTOP, full: true },
  { name: 'stats-dark', route: '/stats', theme: 'dark', size: DESKTOP, full: false },
  { name: 'exercises', route: '/exercises', theme: 'light', size: DESKTOP, full: false },
  { name: 'about', route: '/about', theme: 'light', size: DESKTOP, full: false },
];

const selected = only.length ? SHOTS.filter((s) => only.some((o) => s.name.startsWith(o))) : SHOTS;
await mkdir(outDir, { recursive: true });

const browser = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
);
let violations = 0;

for (const shot of selected) {
  const context = await browser.newContext({
    viewport: shot.size,
    colorScheme: shot.theme,
    deviceScaleFactor: 1,
  });
  if (process.env.SCREENSHOT_PROXY_FONTS === '1') {
    await context.route(/^https:\/\/fonts\.(googleapis|gstatic)\.com\//, async (route) => {
      const request = route.request();
      const response = await fetch(request.url(), {
        headers: { 'user-agent': request.headers()['user-agent'] ?? '' },
      });
      await route.fulfill({
        status: response.status,
        body: Buffer.from(await response.arrayBuffer()),
        headers: {
          'content-type': response.headers.get('content-type') ?? 'application/octet-stream',
          'access-control-allow-origin': '*',
        },
      });
    });
  }
  const page = await context.newPage();
  page.on('pageerror', (error) => console.error(`  ! ${shot.name}: ${error.message}`));
  await page.goto(`${base}#${shot.route}`, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(700);
  if (shot.actions) await shot.actions(page);
  const file = resolve(outDir, `${shot.name}.png`);
  await page.screenshot({ path: file, fullPage: shot.full });
  console.log(`✓ ${shot.name} → ${file}`);

  if (runAxe) {
    const result = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();
    for (const v of result.violations) {
      violations += v.nodes.length;
      console.log(`  axe [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length})`);
      for (const node of v.nodes.slice(0, 3)) console.log(`      ${node.target.join(' ')}`);
    }
  }
  await context.close();
}

await browser.close();
if (runAxe) {
  console.log(
    violations === 0 ? 'axe: нарушений WCAG A/AA не найдено' : `axe: ${violations} нарушений`,
  );
  process.exitCode = violations === 0 ? 0 : 1;
}
