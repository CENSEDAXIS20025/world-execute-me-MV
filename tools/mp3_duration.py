#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯 Python 解析 MP3 时长，不依赖 ffmpeg / ffprobe / mutagen。

来源：生成 world.execute(me)-MV.html 的那次会话
（session-4e991631，turn 1 step 6）。当时环境里没有 ffmpeg/ffprobe，
模型就手写了一个 MPEG 音频帧解析器来拿到准确时长，再用它校准 MV 的时间轴。

用法:
    python mp3_duration.py "Mili - world.execute (me) ;.mp3"

与原始脚本的差异（已注明，便于追溯）:
  1. 音频路径改为命令行参数，不再硬编码会话里的桌面路径。
  2. 时长用帧头里实际读到的采样率计算，不再硬编码 44100
     （对 44100 的文件结果相同，对 48k / 22.05k 才正确）。
  3. 修正了 Layer I / Layer III 的帧长分支：原脚本把这两个分支写反了。
     在 Layer III 上它用 Layer I 的公式（帧长只有真实的 1/3），又把每帧
     采样数记成 384 而非 1152 —— 两个错误在"总采样数"上恰好互相抵消，
     所以原脚本给出的时长仍是对的，但逐帧游走是错位的。这里按规范修正。
"""
import struct
import sys

# MPEG 音频帧头查表
BITRATES = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
RATES = {
    3: {0: 44100, 1: 48000, 2: 32000},   # MPEG 1
    2: {0: 22050, 1: 24000, 2: 16000},   # MPEG 2
    0: {0: 11025, 1: 12000, 2: 8000},    # MPEG 2.5
}


def analyze(path):
    data = open(path, 'rb').read()
    r = {'file': path, 'bytes': len(data)}

    # ---- 1. Xing / Info 头。VBR 文件里带总帧数，是最省事的时长来源 ----
    i = data.find(b'Xing')
    if i < 0:
        i = data.find(b'Info')
    r['xing_at'] = i
    if i >= 0 and i + 8 <= len(data):
        tag = data[i:i + 120]
        flags = struct.unpack('>I', tag[4:8])[0]
        r['xing_flags'] = flags
        pos = 8
        if flags & 1:
            r['xing_frames'] = struct.unpack('>I', tag[pos:pos + 4])[0]
            pos += 4
        if flags & 2:
            r['xing_bytes'] = struct.unpack('>I', tag[pos:pos + 4])[0]
            pos += 4
        if flags & 4:
            pos += 100                      # 跳过 TOC 表
        if flags & 8:
            r['xing_quality'] = struct.unpack('>I', tag[pos:pos + 4])[0]
            pos += 4

    # ---- 2. 逐帧走一遍，按帧长累加采样数 ----
    idx = 0
    frames = 0
    samples = 0
    rate_used = None
    while idx + 4 <= len(data):
        if data[idx] != 0xff or (data[idx + 1] & 0xe0) != 0xe0:
            idx += 1
            continue
        b = data[idx + 1:idx + 4]
        ver = (b[0] >> 3) & 3        # 3 = MPEG1, 2 = MPEG2, 0 = MPEG2.5
        lay = (b[0] >> 1) & 3        # 3 = Layer I, 2 = Layer II, 1 = Layer III
        if ver == 1 or lay == 0:     # 保留值，不是有效帧
            idx += 1
            continue
        br = (b[1] >> 4) & 15
        sr = (b[1] >> 2) & 3
        pad = (b[1] >> 1) & 1
        if br == 0 or br == 15 or sr == 3:
            idx += 1
            continue

        kbps = BITRATES[br]
        rate = RATES[ver][sr]
        if lay == 3:                                    # Layer I
            n = 384
            fs = (12 * kbps * 1000 // rate + pad) * 4
        elif lay == 2:                                  # Layer II
            n = 1152
            fs = 144 * kbps * 1000 // rate + pad
        else:                                           # Layer III
            n = 1152 if ver == 3 else 576
            fs = (144 if ver == 3 else 72) * kbps * 1000 // rate + pad

        if fs <= 0 or idx + fs > len(data):
            idx += 1
            continue
        frames += 1
        samples += n
        idx += fs
        rate_used = rate

    r['frames'] = frames
    r['samples'] = samples
    r['sample_rate'] = rate_used
    if rate_used:
        r['duration_sec'] = samples / float(rate_used)
    if r.get('xing_frames') and rate_used:
        # 交叉验证：Xing 里的总帧数 × 每帧采样数
        r['duration_from_xing_sec'] = r['xing_frames'] * 1152 / float(rate_used)
    return r


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    r = analyze(sys.argv[1])
    order = ('bytes', 'duration_sec', 'frames', 'sample_rate',
             'duration_from_xing_sec', 'xing_at', 'xing_frames', 'xing_bytes',
             'xing_flags', 'xing_quality')
    for k in order:
        if k in r:
            print('%-24s %s' % (k, r[k]))
    if 'duration_sec' in r:
        m, s = divmod(r['duration_sec'], 60)
        print('%-24s %d:%05.2f' % ('duration', m, s))
    return 0


if __name__ == '__main__':
    sys.exit(main())
