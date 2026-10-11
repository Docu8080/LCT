// Browser workflows and text contrast on a disposable local demo; no browser package needed.
// node tests/audit_contrast.mjs [report.json]; FSP_BASE_URL, CHROME_PATH override defaults.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { checkIntegration } from './browser_integration.mjs';

export function contrastRatio(a, b) {
  const luminance = (rgb) =>
    rgb
      .map((x) => x / 255)
      .map((x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4))
      .reduce((sum, x, i) => sum + x * [0.2126, 0.7152, 0.0722][i], 0);
  const x = luminance(a),
    y = luminance(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}
function inspectDocument() {
  const parse = (color) => {
    const values = color.match(/[\d.]+/g)?.map(Number);
    return values?.length >= 3 ? [...values.slice(0, 3), values[3] ?? 1] : null;
  };
  const blend = (a, b) => a.slice(0, 3).map((x, i) => x * a[3] + b[i] * (1 - a[3]));
  const failures = [],
    skipped = [],
    seen = new Set();
  let checked = 0;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode,
      el = node.parentElement,
      text = node.textContent.trim();
    if (
      !text ||
      !el ||
      seen.has(el) ||
      el.closest('script,style,[aria-hidden=true],button[disabled],[aria-disabled=true]')
    )
      continue;
    seen.add(el);
    const style = getComputedStyle(el),
      rect = el.getBoundingClientRect();
    if (!rect.width || !rect.height || style.visibility !== 'visible') continue;
    const layers = [];
    let uncertain = false;
    for (let ancestor = el; ancestor; ancestor = ancestor.parentElement) {
      const s = getComputedStyle(ancestor);
      if (s.backgroundImage !== 'none' || Number(s.opacity) < 1 || s.filter !== 'none') {
        uncertain = true;
        break;
      }
      const color = parse(s.backgroundColor);
      if (color) {
        layers.push(color);
        if (color[3] === 1) break;
      }
    }
    if (uncertain) {
      skipped.push(text.slice(0, 60));
      continue;
    }
    const foreground = parse(style.color);
    if (!foreground) {
      skipped.push(text.slice(0, 60));
      continue;
    }
    let background = [255, 255, 255];
    for (const layer of layers.reverse()) background = blend(layer, background);
    const ratio = contrastRatio(blend(foreground, background), background);
    const large =
        parseFloat(style.fontSize) >= 24 ||
        (Number(style.fontWeight) >= 700 && parseFloat(style.fontSize) >= 18.6667),
      minimum = large ? 3 : 4.5;
    checked++;
    if (ratio < minimum)
      failures.push({
        text: text.slice(0, 80),
        class: el.className,
        foreground: style.color,
        background: background.map(Math.round),
        ratio: +ratio.toFixed(2),
        minimum,
      });
  }
  // ponytail: ancestor backgrounds only; gradients, overlap, pseudo-elements and images need visual review.
  return { checked, failures, skipped };
}
if (process.argv.includes('--self-test')) {
  assert.equal(contrastRatio([0, 0, 0], [255, 255, 255]), 21);
  assert.equal(contrastRatio([255, 255, 255], [255, 255, 255]), 1);
  assert.ok(contrastRatio([95, 107, 125], [255, 255, 255]) >= 4.5);
  assert.ok(contrastRatio([170, 170, 170], [255, 255, 255]) < 4.5);
  console.log('Contrast calculations verified');
} else {
  const root = path.dirname(path.dirname(fileURLToPath(import.meta.url))),
    base = process.env.FSP_BASE_URL || 'http://127.0.0.1:8080';
  const chrome =
    process.env.CHROME_PATH ||
    (process.platform === 'win32'
      ? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
      : process.platform === 'darwin'
        ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        : 'google-chrome');
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ltn-contrast-')),
    sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const child = spawn(
    chrome,
    [
      '--headless=new',
      '--disable-gpu',
      '--disable-extensions',
      ...(process.env.CHROME_NO_SANDBOX === '1' ? ['--no-sandbox'] : []),
      '--remote-debugging-port=0',
      `--user-data-dir=${profile}`,
      '--no-first-run',
      '--no-default-browser-check',
      'about:blank',
    ],
    { stdio: 'ignore', windowsHide: true }
  );
  let ws;
  const pending = new Map();
  const browserErrors = [];
  let nextId = 0;
  try {
    let port;
    for (let i = 0; i < 60; i++) {
      try {
        port = fs.readFileSync(path.join(profile, 'DevToolsActivePort'), 'utf8').split('\n')[0];
        break;
      } catch {
        await sleep(100);
      }
    }
    if (!port) throw new Error('Chrome did not start. Set CHROME_PATH to your browser executable.');
    const tabs = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    ws = new WebSocket(tabs.find((tab) => tab.type === 'page').webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });
    ws.onmessage = (message) => {
      const data = JSON.parse(message.data),
        task = pending.get(data.id);
      if (data.method === 'Runtime.exceptionThrown')
        browserErrors.push(
          data.params.exceptionDetails.exception?.description || data.params.exceptionDetails.text
        );
      if (data.method === 'Network.responseReceived' && data.params.response.status >= 500)
        browserErrors.push(`${data.params.response.status}: ${data.params.response.url}`);
      if (task) {
        pending.delete(data.id);
        clearTimeout(task.timeout);
        data.error ? task.reject(new Error(data.error.message)) : task.resolve(data.result);
      }
    };
    const send = (method, params = {}) =>
      new Promise((resolve, reject) => {
        const id = ++nextId;
        pending.set(id, {
          resolve,
          reject,
          timeout: setTimeout(() => {
            pending.delete(id);
            reject(new Error(method + ' timed out'));
          }, 10000),
        });
        ws.send(JSON.stringify({ id, method, params }));
      });
    const evaluate = async (expression) => {
      const result = await send('Runtime.evaluate', {
        expression,
        awaitPromise: true,
        returnByValue: true,
      });
      if (result.exceptionDetails)
        throw new Error(
          result.exceptionDetails.exception?.description || result.exceptionDetails.text
        );
      return result.result.value;
    };
    await send('Browser.getVersion');
    await send('Page.enable');
    await send('Runtime.enable');
    await send('Network.enable');
    await send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 1000,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await send('Emulation.setEmulatedMedia', {
      features: [{ name: 'prefers-reduced-motion', value: 'reduce' }],
    });
    await send('Page.navigate', { url: base });
    await sleep(500);
    const workspaceRoutes = new Set([
      'overview',
      'profile',
      'tests',
      'invitations',
      'tasks',
      'jobs',
      'settings',
      'matching',
      'needs',
      'company',
    ]);
    const visit = async (route) => {
      await evaluate(`location.hash=${JSON.stringify(route)}`);
      await sleep(150);
      for (let i = 0; i < 100; i++) {
        if (
          await evaluate(
            `!!document.querySelector(${JSON.stringify(workspaceRoutes.has(route) ? '#content' : '#public-content')})&&!document.querySelector('.loading-skeleton')`
          )
        ) {
          if (await evaluate(`!!document.querySelector('#content .errorpage')`))
            throw new Error('Page loaded an error: ' + route);
          return;
        }
        await sleep(50);
      }
      throw new Error('Page did not render: ' + route);
    };
    const report = {
      base,
      viewport: '1440×1000',
      limitations: 'Solid ancestor backgrounds only. Skipped text and overlap need manual review.',
      pages: {},
    };
    const audit = async (prefix) => {
      report.pages[prefix] = await evaluate(
        `(()=>{const contrastRatio=${contrastRatio.toString()};return (${inspectDocument.toString()})()})()`
      );
    };
    for (const route of [
      'home',
      'login',
      'register',
      'privacy',
      'terms',
      'consent',
      'help',
      'accessibility',
      'not-found',
    ]) {
      await visit(route);
      await audit('public/' + route);
    }
    await visit('login');
    await evaluate(
      `document.querySelector('[data-action="demo-login"][data-role="candidate"]').click()`
    );
    await visit('overview');
    await visit('profile');
    await evaluate(
      `document.querySelector('form[data-form="profile"] [name="work_format"]').value='any';document.querySelector('form[data-form="profile"]').requestSubmit()`
    );
    await sleep(200);
    await visit('profile');
    assert.equal(
      await evaluate(
        `document.querySelector('form[data-form="profile"] [name="work_format"]').value`
      ),
      'any'
    );
    await evaluate(
      `(async()=>{const blob=await fetch('/api/candidate/profile.pdf').then(r=>r.blob());const transfer=new DataTransfer();transfer.items.add(new File([blob],'resume.pdf',{type:'application/pdf'}));const input=document.querySelector('[data-resume-pdf]');input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));})()`
    );
    for (let i = 0; i < 100; i++) {
      if (await evaluate(`!!document.querySelector('#modal form[data-form="resume-preview"]')`))
        break;
      await sleep(50);
    }
    assert.ok(
      await evaluate(`!!document.querySelector('#modal form[data-form="resume-preview"]')`),
      'PDF preview did not open'
    );
    await evaluate(`document.querySelector('#modal form').requestSubmit()`);
    await sleep(100);
    assert.ok(
      await evaluate(
        `document.querySelector('form[data-form="profile"] [name="skills"]').value.includes('Python')`
      ),
      'PDF fields were not applied'
    );
    await evaluate(`document.querySelector('[data-action="demo-switch"]').click()`);
    await visit('matching');
    assert.equal(
      await evaluate(`fetch('/api/auth/me').then(r=>r.json()).then(u=>u.role)`),
      'employer'
    );
    await evaluate(
      `document.querySelector('[data-action="demo-reset"]').click();document.querySelector('[data-action="demo-reset-confirm"]').click()`
    );
    await sleep(300);
    await visit('matching');
    report.workflow_checks = [
      'Demo button login',
      'PDF upload and editable preview',
      'Applying PDF fields to the form',
      'Role switch',
      'Scenario reset',
      'Any work format survives profile save',
    ];
    for (const [role, routes] of [
      ['candidate', ['overview', 'profile', 'tests', 'invitations', 'tasks', 'jobs', 'settings']],
      ['employer', ['matching', 'needs', 'invitations', 'tasks', 'company', 'settings']],
    ]) {
      await evaluate(
        `(async()=>{const me=await fetch('/api/auth/me').then(r=>r.ok?r.json():null);const r=await fetch('/api/auth/demo',{method:'POST',headers:{'Content-Type':'application/json',...(me?{'X-CSRF-Token':me.csrf}:{})},body:JSON.stringify({role:${JSON.stringify(role)}})});if(!r.ok)throw new Error(await r.text());location.reload();})()`
      );
      await sleep(350);
      for (const route of routes) {
        await visit(route);
        await audit(role + '/' + route);
      }
    }
    report.workflow_checks.push(...(await checkIntegration({ evaluate, visit, send })));
    await visit('matching');
    fs.mkdirSync(path.join(root, 'data'), { recursive: true });
    await send('Page.captureScreenshot', { format: 'png' }).then((r) =>
      fs.writeFileSync(path.join(root, 'data/contrast-desktop.png'), Buffer.from(r.data, 'base64'))
    );
    await send('Emulation.setDeviceMetricsOverride', {
      width: 390,
      height: 844,
      deviceScaleFactor: 1,
      mobile: true,
    });
    await visit('matching');
    await audit('employer/matching-mobile');
    await send('Page.captureScreenshot', { format: 'png' }).then((r) =>
      fs.writeFileSync(path.join(root, 'data/contrast-mobile.png'), Buffer.from(r.data, 'base64'))
    );
    await evaluate(`demoEnabled=false;user=null;history.replaceState(null,'','#login');render()`);
    await sleep(150);
    assert.equal(
      await evaluate(`getComputedStyle(document.querySelector('.demologins')).display`),
      'none'
    );
    report.workflow_checks.push('Disabled demo controls stay hidden');
    await send('Page.navigate', { url: base + '/docs' });
    for (let i = 0; i < 100; i++) {
      if (await evaluate(`!!document.querySelector('#api-paths details')`)) break;
      await sleep(50);
    }
    await evaluate(
      `const search=document.querySelector('#api-search');search.value='resume/preview';search.dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#api-paths details').open=true`
    );
    assert.ok(
      await evaluate(`document.querySelector('#api-paths').textContent.includes('application/pdf')`)
    );
    await audit('api/docs');
    report.workflow_checks.push('API docs describe the PDF body');
    report.browser_errors = browserErrors;
    assert.deepEqual(browserErrors, [], 'Browser exceptions or server errors');
    const output = path.resolve(
      process.argv[2] || path.join(root, 'docs/contrast_browser_results.json')
    );
    fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
    const failures = Object.values(report.pages).reduce((n, page) => n + page.failures.length, 0);
    console.log(
      `${Object.keys(report.pages).length} pages; ${failures} contrast failures; ${output}`
    );
    process.exitCode = failures ? 1 : 0;
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  } finally {
    ws?.close();
    child.kill();
    for (const task of pending.values()) clearTimeout(task.timeout);
    await sleep(200);
    const temporaryRoot = path.resolve(os.tmpdir()) + path.sep;
    if (
      path.resolve(profile).startsWith(temporaryRoot) &&
      path.basename(profile).startsWith('ltn-contrast-')
    )
      try {
        fs.rmSync(profile, { recursive: true, force: true });
      } catch {}
  }
}
