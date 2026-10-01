#!/usr/bin/env node
/*
 * cdp_capture.js -- 用 Chrome DevTools Protocol 给 MV 逐幕截图。
 * 不需要 puppeteer / playwright，只用 Node 内置的 fetch 和 WebSocket。
 *
 * 来源：session-4e991631，turn 1 step 28（原始版本把 14 个时间点硬编码在里面）。
 *
 * 这是那条"自建视觉反馈回路"的核心：把 <audio>.currentTime 直接设到某一幕，
 * 等画面稳定，再通过 Page.captureScreenshot 拿 PNG。截图随后交给
 * ascii_view.py / image_stats.py 变成文本，模型就能"看到"自己画的东西。
 *
 * 用法:
 *   node cdp_capture.js --out .\shots
 *   node cdp_capture.js --port 9334 --url world.execute --out .\shots \
 *        --times "2:boot,20:compile,36:geometry,50:electric"
 */

const fs = require('fs');
const path = require('path');

const sleep = ms => new Promise(r => setTimeout(r, ms));

const DEFAULT_TIMES = [
  [2, 'boot'], [20, 'compile'], [36, 'geometry'], [50, 'electric'],
  [65, 'neural'], [80, 'cute'], [94, 'dual'], [110, 'shatter'],
  [135, 'error'], [152, 'execution'], [168, 'rebuild'], [184, 'equations'],
  [198, 'orbit'], [208, 'shutdown'],
];

function parseArgs(argv) {
  const a = { port: 9334, url: 'world.execute', out: './shots', times: null, settle: 500 };
  for (let i = 2; i < argv.length; i += 2) {
    const k = argv[i].replace(/^--/, '');
    const v = argv[i + 1];
    if (k === 'port') a.port = parseInt(v, 10);
    else if (k === 'url') a.url = v;
    else if (k === 'out') a.out = v;
    else if (k === 'settle') a.settle = parseInt(v, 10);
    else if (k === 'times') {
      a.times = v.split(',').map(s => {
        const [t, name] = s.split(':');
        return [parseFloat(t), name || String(t)];
      });
    }
  }
  return a;
}

(async () => {
  const args = parseArgs(process.argv);
  const times = args.times || DEFAULT_TIMES;
  fs.mkdirSync(args.out, { recursive: true });

  // 1. 找到目标页面
  const targets = await fetch(`http://127.0.0.1:${args.port}/json`).then(r => r.json());
  const page = targets.find(t => t.type === 'page' && t.url.includes(args.url));
  if (!page) {
    console.error('page not found. targets:',
      targets.map(t => `${t.type} ${t.url}`).join('\n  '));
    process.exit(1);
  }

  // 2. 连上 CDP
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

  let id = 0;
  const pending = new Map();
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id) {
      const p = pending.get(m.id);
      if (p) {
        pending.delete(m.id);
        m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result);
      }
    }
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, { resolve, reject });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });

  await send('Runtime.enable');
  await send('Page.enable');

  // 3. 让页面开始播放（MV 需要一次点击才启动 <audio>）
  await send('Runtime.evaluate', { expression: `document.getElementById('start').click();` });
  await sleep(1200);

  // 4. 逐幕定位 + 截图
  for (const [t, name] of times) {
    await send('Runtime.evaluate', { expression: `audio.currentTime=${t};` });
    await sleep(args.settle);
    const shot = await send('Page.captureScreenshot', { format: 'png' });
    const file = path.join(args.out, `_mv_shot_${name}.png`);
    fs.writeFileSync(file, Buffer.from(shot.data, 'base64'));
    const info = await send('Runtime.evaluate', {
      expression: `JSON.stringify({t:audio.currentTime,scene:sceneIndexAt(audio.currentTime),err:document.getElementById('error').classList.contains('hidden')})`,
      returnByValue: true,
    });
    console.log(`${name.padEnd(10)} -> ${file}   ${info.result.value}`);
  }

  ws.close();
  console.log(`\n${times.length} screenshots written to ${args.out}`);
})().catch(e => { console.error('FATAL', e); process.exit(1); });
