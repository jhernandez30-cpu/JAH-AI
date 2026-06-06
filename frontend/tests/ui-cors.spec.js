const { test, expect } = require('@playwright/test');
const path = require('path');

test.describe('JAH AI UI, CORS y herramientas avanzadas', () => {
  test('mantiene identidad visual y conecta backend, uploads y herramientas', async ({ page }) => {
    const FRONTEND_URL = process.env.FRONTEND_URL || 'http://127.0.0.1:5500/asistente-programacion.html';
    const API_BASE = process.env.API_BASE_URL || 'http://127.0.0.1:8787';
    const isProd = !(FRONTEND_URL.includes('localhost') || FRONTEND_URL.includes('127.0.0.1') || FRONTEND_URL.startsWith('file://'));

    const consoleErrors = [];
    const requestStarts = [];
    const requests = [];
    const failed = [];

    page.on('console', msg => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    page.on('request', req => {
      requestStarts.push({ url: req.url(), method: req.method() });
    });
    page.on('requestfinished', async req => {
      const res = await req.response();
      requests.push({ url: req.url(), method: req.method(), status: res ? res.status() : null });
    });
    page.on('requestfailed', req => {
      const failure = req.failure ? req.failure() : { errorText: 'requestfailed' };
      failed.push({ url: req.url(), method: req.method(), failure: failure.errorText });
    });

    await page.goto(FRONTEND_URL, { waitUntil: 'load' });
    await expect(page).toHaveTitle(/JAH AI|Asistente/);
    await expect(page.locator('#assistantTitle')).toHaveText('JAH AI');
    await expect(page.locator('img.sidebar-brand-logo')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('img.empty-state-logo')).toBeVisible({ timeout: 5000 });

    const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
    const closePanelIfOpen = async () => {
      const closeButton = page.locator('#closeAssistantPanelBtn');
      if (await closeButton.isVisible().catch(() => false)) {
        await closeButton.click();
        await expect(page.locator('#assistantPanelOverlay')).toBeHidden();
      }
    };
    const assetPath = path.resolve(__dirname, 'assets', 'test_upload.txt');

    await page.locator('[data-action="system-status"]').click();
    await pause(800);

    const fileInput = page.locator('#fileInput');
    await expect(fileInput).toHaveAttribute('multiple', '');
    await fileInput.setInputFiles(assetPath);
    await pause(1500);

    await page.evaluate(async ({ apiBase, assetName }) => {
      const status = await window.odysseus.status();
      if (!status.ok) throw new Error('status failed');

      const meta = JSON.parse(localStorage.getItem('jah_ai_uploaded_files_meta') || '[]');
      const uploadPath = meta[0]?.relative_path || meta[0]?.path;

      await window.odysseus.files_list();
      await window.odysseus.files_search('test');
      if (uploadPath) await window.odysseus.files_read(uploadPath);

      for (const action of ['analyze', 'code', 'debug', 'plan']) {
        const res = await window.odysseus[action]({
          message: `prueba ${action}`,
          upload_path: uploadPath,
          options: { use_llm: false }
        });
        if (!res.ok) throw new Error(`${action} failed`);
      }
      const tool = await window.odysseus.tools_run('status', {});
      if (!tool.ok) throw new Error('tools_run failed');

      const fd = new FormData();
      fd.append('file', new File(['endpoint directo'], assetName, { type: 'text/plain' }));
      const directUpload = await fetch(`${apiBase}/api/odysseus/files/upload`, { method: 'POST', body: fd });
      if (!directUpload.ok) throw new Error('direct odysseus upload failed');
      const directData = await directUpload.json();
      const directPath = directData.relative_path || directData.path;
      if (directPath) await window.odysseus.files_read(directPath);
    }, { apiBase: API_BASE, assetName: 'test_upload_direct.txt' });

    await closePanelIfOpen();

    await page.locator('#discoverPanelBtn').click();
    await expect(page.locator('#assistantPanelTitle')).toHaveText('Descubrir');
    await expect(page.locator('[data-panel-action="open-panel"][data-target-panel="odysseus"]')).toContainText('Herramientas');
    await page.locator('[data-panel-action="open-panel"][data-target-panel="odysseus"]').click();
    await expect(page.locator('#assistantPanelTitle')).toHaveText('Herramientas avanzadas');
    await expect(page.locator('#assistantPanelKicker')).toHaveText('JAH AI');
    await expect(page.locator('#assistantPanel')).not.toContainText('Odysseus');
    await closePanelIfOpen();

    await page.locator('#historyPanelBtn').click();
    await pause(400);
    await closePanelIfOpen();
    await page.locator('#spacesPanelBtn').click();
    await pause(400);
    await closePanelIfOpen();
    await page.locator('#projectsPanelBtn').click();
    await pause(400);
    await closePanelIfOpen();

    await page.locator('#coachInput').fill('Mensaje de prueba desde Playwright');
    await page.locator('.send-orb').click();
    await pause(1200);
    await page.evaluate(async apiBase => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 1500);
      try {
        const res = await fetch(`${apiBase}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            message: 'Ping de verificacion Playwright',
            session_id: 'playwright-smoke',
            use_rag: false,
            deep_thinking: false,
            smartSearch: false
          })
        });
        if ([404, 405, 500].includes(res.status)) {
          throw new Error(`/api/chat respondio con estado invalido: ${res.status}`);
        }
      } catch (error) {
        if (!error || error.name !== 'AbortError') throw error;
      } finally {
        clearTimeout(timeout);
      }
    }, API_BASE);

    const critical = [
      `${API_BASE}/api/health`,
      `${API_BASE}/api/odysseus/status`,
      `${API_BASE}/api/upload`,
      `${API_BASE}/api/odysseus/files/upload`,
      `${API_BASE}/api/odysseus/files/list`,
      `${API_BASE}/api/odysseus/files/search`,
      `${API_BASE}/api/odysseus/files/read`,
      `${API_BASE}/api/odysseus/analyze`,
      `${API_BASE}/api/odysseus/code`,
      `${API_BASE}/api/odysseus/debug`,
      `${API_BASE}/api/odysseus/plan`,
      `${API_BASE}/api/odysseus/tools/run`,
      `${API_BASE}/api/chat`,
      `${API_BASE}/api/history`,
      `${API_BASE}/api/spaces`,
      `${API_BASE}/api/projects`,
    ];

    const errors = [];
    for (const ep of critical) {
      const found = requests.find(r => r.url.startsWith(ep));
      const started = requestStarts.find(r => r.url.startsWith(ep));
      if (!found && !started) {
        errors.push(`No se detecto llamada a endpoint critico: ${ep}`);
        continue;
      }
      if (found && [404, 405, 500].includes(found.status)) {
        errors.push(`Endpoint ${ep} respondio con estado invalido: ${found.status}`);
      }
    }

    if (isProd) {
      for (const req of [...requestStarts, ...requests]) {
        if (req.url.includes('127.0.0.1') || req.url.includes('localhost')) {
          errors.push(`Llamada a localhost detectada en produccion: ${req.url}`);
        }
      }
    }
    consoleErrors.forEach(error => errors.push(`Console error: ${error}`));
    failed
      .filter(item => !(
        item.failure === 'net::ERR_ABORTED'
        && (
          item.url.startsWith(`${API_BASE}/api/chat`)
          || item.url.startsWith(`${API_BASE}/api/auth/providers`)
        )
      ))
      .forEach(item => errors.push(`Request failed: ${item.url} - ${item.failure}`));

    if (errors.length) {
      console.log('Requests captured:', JSON.stringify(requests, null, 2));
      console.log('Failed requests:', JSON.stringify(failed, null, 2));
      throw new Error(errors.join('\n'));
    }
  });
});
