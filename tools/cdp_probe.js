#!/usr/bin/env node
/*
 * cdp_probe.js -- 通过 CDP 给运行中的 MV 做一次体检。
 *
 * 来源：session-4e991631，turn 1 step 24 与 step 27。
 *
 * 检查项：文档就绪状态、audio.duration 是否解出来、三个浮层是否处于正确状态、
 * canvas 实际分辨率与 DPR、拖动时间轴过程中的 JS 异常和控制台报错。
 * 用于在截图之前先确认"页面本身没坏"，避免把渲染 bug 误判成画面问题。
 *
 * 用法:
 *   node cdp_probe.js
 *   node cdp_probe.js --port 9334 --url world.execute --seek "1,20,60,120,180,208"
 */

const sleep = ms => new Promise(r => setTimeout(r, ms));

function parseArgs(argv) {
  const a = { port: 9334, url: 'world.execute', seek: '1,20,40,60,80,100,120,140,155,175,195,209' };
  for (let i = 2; i < argv.length; i += 2) {
    const k = argv[i].replace(/^--/, '');
    const v = argv[i + 1];
    if (k === 'port') a.port = parseInt(v, 10);
    else if (k === 'url') a.url = v;
    else if (k === 'seek') a.seek = v;
  }
  return a;
}

(async () => {
  const args = parseArgs(process.argv);
  const targets = await fetch(`http://127.0.0.1:${args.port}/json`).then(r => r.json());
  const page = targets.find(t => t.type === 'page' && t.url.includes(args.url));
  if (!page) { console.error('page not found'); process.exit(1); }

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

  let id = 0;
  const pending = new Map();
  const exceptions = [];
  const consoleErrs = [];

  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id) {
      const p = pending.get(m.id);
      if (p) {
        pending.delete(m.id);
        m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result);
      }
    } else if (m.method === 'Runtime.exceptionThrown') {
      exceptions.push(m.params.exceptionDetails.text + ' ' +
        (m.params.exceptionDetails.exception && m.params.exceptionDetails.exception.description || ''));
    } else if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
      consoleErrs.push(m.params.args.map(a => a.value || a.description).join(' '));
    }
  };

  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, { resolve, reject });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });

  await send('Runtime.enable');
  await send('Log.enable');
  await send('Page.enable');
  await sleep(3500);

  const pre = await send('Runtime.evaluate', {
    expression: `JSON.stringify({
      ready: document.readyState,
      dur: audio.duration,
      srcPrefix: audio.src.slice(0, 30),
      errHidden: document.getElementById('error').classList.contains('hidden')
    })`,
    returnByValue: true,
  });
  console.log('BEFORE ', pre.result.value);

  await send('Runtime.evaluate', { expression: `document.getElementById('start').click();` });
  await sleep(1800);

  const seeks = args.seek.split(',').map(s => parseFloat(s));
  for (const t of seeks) {
    await send('Runtime.evaluate', {
      expression: `try{audio.currentTime=${t};}catch(e){window.__seekErr=e.message;}`,
    });
    await sleep(330);
  }

  const post = await send('Runtime.evaluate', {
    expression: `JSON.stringify({
      startHidden: document.getElementById('start').classList.contains('hidden'),
      errorHidden: document.getElementById('error').classList.contains('hidden'),
      replayHidden: document.getElementById('replay').classList.contains('hidden'),
      audioT: audio.currentTime,
      audioPaused: audio.paused,
      canvasW: canvas.width,
      canvasH: canvas.height,
      dpr: DPR,
      seekErr: window.__seekErr || null
    })`,
    returnByValue: true,
  });
  console.log('AFTER  ', post.result.value);
  console.log('EXCEPTIONS', JSON.stringify(exceptions, null, 2));
  console.log('CONSOLE_ERR', JSON.stringify(consoleErrs, null, 2));

  ws.close();
  process.exit(exceptions.length ? 2 : 0);
})().catch(e => { console.error('FATAL', e); process.exit(1); });
