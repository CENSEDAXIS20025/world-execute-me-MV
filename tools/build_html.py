#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把分段写出的 HTML 拼回单文件，并把 MP3 以内嵌 data URI 的形式注入。

来源：session-4e991631，turn 1 step 13（拼接分段 + node --check）
与 step 20（注入真实音频）、step 17（注入静音 WAV 做快速调试）。

为什么需要它：11 MB 的 base64 不该走一遍模型的上下文窗口。做法是 HTML 里
留一个 `__AUDIO_BASE64__` 占位符，最后在磁盘上把编码好的音频拼进去。

用法:
  # 1) 只拼接分段，产出带占位符的模板
  python build_html.py --parts p1.html p2.html p3.html --template-only --out template.html

  # 2) 注入真实音频，产出可双击播放的成品
  python build_html.py --template template.html --audio "song.mp3" --out mv.html

  # 3) 调试用：注入 N 秒静音 WAV，避免每次都 base64 编码 8 MB
  python build_html.py --template template.html --silence 220 --out test.html
"""
import argparse
import base64
import os
import struct
import sys
import time

PLACEHOLDER = '__AUDIO_BASE64__'
MP3_LINE = 'const AUDIO_SRC = "data:audio/mpeg;base64,' + PLACEHOLDER + '";'


def concat_parts(paths):
    """把分段文件按顺序拼成一个模板字符串。"""
    chunks = []
    for p in paths:
        with open(p, encoding='utf-8') as f:
            chunks.append(f.read())
    return '\n'.join(chunks)


def silent_wav(seconds, sample_rate=8000):
    """生成一段 N 秒的 8-bit 单声道静音 WAV，base64 后当占位音频用。

    来自原始脚本 step 17：调试布局/时间轴时不需要真的解码 8 MB MP3，
    一个 220 秒的静音 WAV 就能让 <audio> 的 duration 接近真实值。
    """
    n = int(sample_rate * seconds)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + n, b'WAVE', b'fmt ', 16,
        1, 1, sample_rate, sample_rate, 1, 8, b'data', n)
    return base64.b64encode(header + bytes(n)).decode('ascii')


def inject(template, b64, mime='audio/mpeg'):
    """把 base64 音频塞进占位符。返回 (新内容, 是否命中占位符)。"""
    if PLACEHOLDER not in template:
        # 兼容已经是真实 data URI 的模板：整行替换
        raise SystemExit('模板里找不到占位符 %s' % PLACEHOLDER)
    src = 'data:%s;base64,%s' % (mime, b64)
    return template.replace(MP3_LINE, 'const AUDIO_SRC = "%s";' % src), True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--parts', nargs='*', help='按顺序拼接的分段文件')
    ap.add_argument('--template', help='已拼接好的模板（含占位符）')
    ap.add_argument('--template-only', action='store_true',
                    help='只拼接，不注入音频')
    ap.add_argument('--audio', help='要内嵌的 MP3')
    ap.add_argument('--silence', type=float, help='改为注入 N 秒静音 WAV')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    t0 = time.time()

    if a.template:
        template = open(a.template, encoding='utf-8').read()
        source = a.template
    elif a.parts:
        template = concat_parts(a.parts)
        source = '%d parts' % len(a.parts)
    else:
        raise SystemExit('需要 --parts 或 --template 之一')

    print('模板来源   : %s' % source)
    print('模板字节数 : %d' % len(template.encode('utf-8')))
    print('含占位符   : %s' % (PLACEHOLDER in template))

    if a.template_only:
        out = template
    elif a.silence:
        b64 = silent_wav(a.silence)
        out, _ = inject(template, b64, mime='audio/wav')
        print('静音 WAV   : %.0f 秒, base64 %d 字符' % (a.silence, len(b64)))
    elif a.audio:
        raw = open(a.audio, 'rb').read()
        b64 = base64.b64encode(raw).decode('ascii')
        out, _ = inject(template, b64)
        print('音频       : %d 字节 -> base64 %d 字符' % (len(raw), len(b64)))
    else:
        raise SystemExit('需要 --audio / --silence / --template-only 之一')

    # newline='' 保证不把 \n 改写成 \r\n，否则内嵌数据的字节数会变
    with open(a.out, 'w', encoding='utf-8', newline='') as f:
        f.write(out)

    print('已写出     : %s' % a.out)
    print('文件字节数 : %d' % os.path.getsize(a.out))
    print('耗时       : %.2f 秒' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
