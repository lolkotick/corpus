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

/** Начать проверку выборки из 30 пар (seed по умолчанию) — для снимков режима «Проверка». */
async function startReview(page) {
  await page.getByLabel('Эксперт (имя или код)').fill('демо');
  await page.getByRole('button', { name: 'Начать проверку' }).click();
  await page.waitForTimeout(300);
}

/** Начать тест под демонстрационным кодом участника. */
async function startTest(page) {
  await page.getByLabel('Имя или код участника').fill('S01');
  await page.getByRole('button', { name: /^Начать/ }).click();
  await page.waitForTimeout(300);
}

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
  {
    name: 'exercises-zh',
    route: '/exercises',
    theme: 'light',
    size: DESKTOP,
    full: false,
    actions: async (page) => {
      await page.getByLabel(/Счётные слова/).check();
      await page.getByRole('button', { name: /^Начать/ }).click();
      await page.getByRole('button', { name: 'Показать подсказку (перевод)' }).click();
      await page
        .getByRole('group', { name: 'Варианты ответа' })
        .getByRole('button')
        .first()
        .click();
      await page.waitForTimeout(500);
    },
  },
  {
    name: 'exercises-ru-mobile',
    route: '/exercises',
    theme: 'dark',
    size: MOBILE,
    full: false,
    actions: async (page) => {
      await page.getByLabel(/Падежи/).check();
      await page.getByRole('button', { name: /^Начать/ }).click();
      await page.keyboard.type('книгу');
      await page.keyboard.press('Enter');
      await page.waitForTimeout(500);
    },
  },
  {
    name: 'exercises-print',
    route: '/exercises/print?kind=mixed&n=6&seed=7',
    theme: 'light',
    size: DESKTOP,
    full: true,
  },
  { name: 'review-setup', route: '/review', theme: 'light', size: DESKTOP, full: false },
  {
    name: 'review',
    route: '/review',
    theme: 'light',
    size: DESKTOP,
    full: true,
    actions: async (page) => {
      await startReview(page);
      // Выравнивание EN–ZH верно, EN–RU — исправить (матрица), артикли верны,
      // 量词 — по одной, падежи — по одной с исправлением второй пометки.
      await page.keyboard.press('1');
      await page.keyboard.press('3');
      await page.keyboard.press('ArrowDown');
      await page.keyboard.press('1');
      await page.keyboard.press('2');
      await page.keyboard.press('ArrowDown');
      await page.keyboard.press('ArrowDown');
      await page.keyboard.press('2');
      await page.keyboard.press('1');
      await page.keyboard.press('3');
      await page.keyboard.press('Escape');
      await page.waitForTimeout(300);
    },
  },
  {
    name: 'review-dark',
    route: '/review',
    theme: 'dark',
    size: DESKTOP,
    full: false,
    actions: async (page) => {
      await startReview(page);
      await page.keyboard.press('1');
      await page.keyboard.press('1');
      await page.keyboard.press('2');
      await page.waitForTimeout(300);
    },
  },
  {
    name: 'review-mobile',
    route: '/review',
    theme: 'light',
    size: MOBILE,
    full: false,
    actions: async (page) => {
      await startReview(page);
      await page.waitForTimeout(300);
    },
  },
  { name: 'test-start', route: '/exercises/test', theme: 'light', size: DESKTOP, full: false },
  {
    name: 'test-task',
    route: '/exercises/test',
    theme: 'light',
    size: DESKTOP,
    full: false,
    actions: async (page) => {
      await startTest(page);
      await page.keyboard.press('1');
      await page.waitForTimeout(300);
    },
  },
  {
    name: 'test-result',
    route: '/exercises/test',
    theme: 'dark',
    size: DESKTOP,
    full: false,
    actions: async (page) => {
      await startTest(page);
      for (let i = 0; i < 15; i += 1) {
        const input = page.locator('#test-answer');
        if ((await input.count()) > 0) {
          await input.fill('ответ');
          await input.press('Enter');
        } else {
          await page.keyboard.press(String((i % 3) + 1));
        }
        await page.waitForTimeout(80);
      }
      await page.waitForTimeout(300);
    },
  },
  {
    name: 'test-mobile',
    route: '/exercises/test',
    theme: 'light',
    size: MOBILE,
    full: false,
    actions: async (page) => {
      await startTest(page);
      await page.keyboard.press('2');
      await page.keyboard.press('1');
      await page.waitForTimeout(300);
    },
  },
  { name: 'about', route: '/about', theme: 'light', size: DESKTOP, full: false },
  { name: 'pair-mobile', route: '/pair/example-018', theme: 'light', size: MOBILE, full: false },
  {
    name: 'menu-mobile',
    route: '/stats',
    theme: 'dark',
    size: MOBILE,
    full: false,
    actions: async (page) => {
      await page.getByRole('button', { name: 'Открыть меню' }).click();
      await page.waitForTimeout(300);
    },
  },
  { name: 'not-found', route: '/nope', theme: 'light', size: DESKTOP, full: false },
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
  if (shot.full) {
    // Иначе липкая шапка окажется посреди снимка всей страницы.
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    await page.waitForTimeout(200);
  }
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
