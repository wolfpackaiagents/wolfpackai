import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:5174';
const API_KEY = 'pk-wp-dev:dev-secret';
const OUT = '/Users/alvarobrito/Documents/desenvolvimento/projetos/github/alvaro-brito-products/wolfpack-ai/website/public/screenshots';

const pages = [
  { route: '/', name: 'overview', wait: 'h1' },
  { route: '/mesh', name: 'mesh', wait: 'h1' },
  { route: '/chat', name: 'chat', wait: 'h1' },
  { route: '/channels', name: 'channels', wait: 'h1' },
  { route: '/schedules', name: 'schedules', wait: 'h1' },
  { route: '/traces', name: 'traces', wait: 'h1' },
  { route: '/sessions', name: 'sessions', wait: 'h1' },
  { route: '/approvals', name: 'approvals', wait: 'h1' },
  { route: '/guardrails', name: 'guardrails', wait: 'h1' },
  { route: '/scores', name: 'scores', wait: 'h1' },
  { route: '/resilience', name: 'resilience', wait: 'h1' },
  { route: '/privacy', name: 'privacy', wait: 'h1' },
  { route: '/settings', name: 'settings', wait: 'h1' },
];

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await page.addInitScript((key) => {
    localStorage.clear();
    localStorage.setItem('wolfpack_api_key', key);
  }, API_KEY);

  for (const p of pages) {
    console.log(`  Taking ${p.name}...`);
    try {
      await page.goto(`${BASE}${p.route}`, { waitUntil: 'networkidle', timeout: 15000 });
      await page.waitForSelector(p.wait, { timeout: 10000 }).catch(() => {});
      await page.waitForTimeout(1000);
      await page.screenshot({ path: `${OUT}/${p.name}.png`, fullPage: false });
      console.log(`    OK`);
    } catch (e: any) {
      console.log(`    FAIL: ${e.message?.slice(0, 60)}`);
    }
  }

  await browser.close();
}

main().catch(console.error);