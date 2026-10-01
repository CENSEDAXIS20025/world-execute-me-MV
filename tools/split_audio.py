#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把内嵌 base64 音频的单文件 HTML 拆成「外链音频 + 精简 HTML」。

这是 build_html.py 的逆操作：
    build_html.py   : 分段 HTML + MP3  --注入-->  单文件 HTML
    split_audio.py  : 单文件 HTML      --拆出-->  精简 HTML + 独立音频文件

用途：11.4 MB 的单文件版本适合分发/双击即播，但不利于阅读、diff 和编辑
（99.4% 的体积是一行 base64）。拆开后 HTML 只剩几十 KB 的源码。

用法:
    python split_audio.py "world.execute(me)-MV.html" --out-dir external-audio
    python split_audio.py in.html --out-dir out --audio-name audio.mp3 --no-guard

关于 `file://` 的坑（实测结论）:
    把音频换成外链后，从 file:// 直接打开时浏览器会把该媒体视为跨源：
    `createMediaElementSource()` **不会抛异常**，但频谱恒为 0、输出静音 ——
    也就是"看起来一切正常，其实没声音，卡点也不动"。
    因此本脚本默认会往拆出的 HTML 里注入一段守卫：检测到
    「非 data: 音频 + file://」时直接跳过 Web Audio，让 <audio> 走原生播放
    （有声音），节拍检测自动回退到 fallbackBeat()。用 http 打开则不受影响。
    用 --no-guard 可以关掉这个注入。
"""
import argparse
import base64
import hashlib
import os
import re
import sys

SRC_RE = re.compile(
    r'const AUDIO_SRC = "data:(?P<mime>audio/[A-Za-z0-9.+-]+);base64,(?P<b64>[A-Za-z0-9+/=]+)";'
)

# 锚点：initAudioGraph 的开头两行
GUARD_RE = re.compile(
    r'(function initAudioGraph\(\)\{\s*\r?\n\s*if\(audioCtx \|\| audioFailed\) return;)'
)

GUARD = """
  /* [split_audio.py 注入] 外链音频 + file:// 的跨源限制：
     浏览器会把 file:// 媒体当作跨源，createMediaElementSource() 不报错，
     但频谱恒为 0 且输出静音。此时放弃 Web Audio，让 <audio> 走原生播放，
     节拍检测自动回退到 fallbackBeat()。用 http 打开则不受影响。 */
  if(AUDIO_SRC.indexOf('data:') !== 0 && location.protocol === 'file:'){
    analyser = null;
    return;
  }"""

EXT = {
    'audio/mpeg': '.mp3',
    'audio/mp3': '.mp3',
    'audio/wav': '.wav',
    'audio/x-wav': '.wav',
    'audio/ogg': '.ogg',
    'audio/mp4': '.m4a',
    'audio/aac': '.aac',
}


def split(src_html, out_dir, audio_name=None, html_name=None, guard=True):
    text = open(src_html, encoding='utf-8').read()
    m = SRC_RE.search(text)
    if not m:
        raise SystemExit('在 %s 里找不到内嵌的 data:audio/...;base64 音频' % src_html)

    mime = m.group('mime')
    b64 = m.group('b64')
    data = base64.b64decode(b64)

    if not audio_name:
        audio_name = 'audio' + EXT.get(mime, '.bin')
    if not html_name:
        html_name = os.path.basename(src_html)

    # 换掉 data URI，改为相对路径引用
    slim = text[:m.start()] + 'const AUDIO_SRC = "%s";' % audio_name + text[m.end():]

    guard_applied = False
    if guard:
        slim, n = GUARD_RE.subn(lambda mo: mo.group(1) + GUARD, slim, count=1)
        guard_applied = (n == 1)
        if not guard_applied:
            raise SystemExit(
                '找不到 initAudioGraph 的锚点，无法注入守卫。'
                '请检查源 HTML 是否被改动过，或用 --no-guard 跳过。')

    os.makedirs(out_dir, exist_ok=True)
    audio_path = os.path.join(out_dir, audio_name)
    html_path = os.path.join(out_dir, html_name)

    # 音频用二进制写；HTML 用 newline='' 避免把 \n 改写成 \r\n
    with open(audio_path, 'wb') as f:
        f.write(data)
    with open(html_path, 'w', encoding='utf-8', newline='') as f:
        f.write(slim)

    return {
        'mime': mime,
        'audio_path': audio_path,
        'audio_bytes': len(data),
        'audio_sha256': hashlib.sha256(data).hexdigest().upper(),
        'html_path': html_path,
        'html_bytes': os.path.getsize(html_path),
        'src_bytes': os.path.getsize(src_html),
        'base64_chars': len(b64),
        'guard_applied': guard_applied,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('html', help='含内嵌 base64 音频的单文件 HTML')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--audio-name', help='拆出的音频文件名（默认按 MIME 推断）')
    ap.add_argument('--html-name', help='拆出的 HTML 文件名（默认与源同名）')
    ap.add_argument('--no-guard', action='store_true',
                    help='不注入 file:// 的 Web Audio 守卫')
    a = ap.parse_args()

    r = split(a.html, a.out_dir, a.audio_name, a.html_name, not a.no_guard)

    print('MIME            : %s' % r['mime'])
    print('base64 chars    : %d' % r['base64_chars'])
    print('audio -> %s' % r['audio_path'])
    print('   %d bytes   SHA256 %s' % (r['audio_bytes'], r['audio_sha256']))
    print('html  -> %s' % r['html_path'])
    print('   %d bytes   (source %d bytes, %.2f%%)'
          % (r['html_bytes'], r['src_bytes'], r['html_bytes'] / float(r['src_bytes']) * 100))
    print('file:// guard   : %s' % ('injected' if r['guard_applied'] else 'not injected'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
