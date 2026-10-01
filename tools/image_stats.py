#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""量化截图：亮度统计、非黑像素占比、亮区包围盒、逐行亮像素分布。

来源：session-4e991631，turn 1 step 29（均值/标准差/非黑占比）与
step 33（亮像素包围盒 + 逐行直方图）。

为什么除了 ASCII 画还要这个：ASCII 画看"形状"，指标看"异常"。
比如 nonblack% 突然掉到 0.1 说明这一幕几乎全黑（渲染挂了），
或包围盒贴到画布边缘说明构图出界。数字比肉眼更早发现这类问题。

用法:
    python image_stats.py shots/
    python image_stats.py shots/_mv_shot_*.png
    python image_stats.py shots/ --rows --threshold 60

与原始脚本的差异：不再用已废弃的 Image.getdata()（Pillow 14 将移除），
改用 tobytes() 直接切片统计；阈值与是否打印逐行分布改为参数。
"""
import argparse
import glob
import os
import sys

from PIL import Image


def frames_from_args(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += sorted(glob.glob(os.path.join(p, '*.png')))
        else:
            out += sorted(glob.glob(p)) or [p]
    return out


def stats(path, bright_threshold=90):
    im = Image.open(path).convert('RGB')
    W, H = im.size
    n = W * H

    raw = im.tobytes()                     # RGB，每像素 3 字节
    r = raw[0::3]
    g = raw[1::3]
    b = raw[2::3]

    mean = (sum(r) // n, sum(g) // n, sum(b) // n)
    var = (sum((v - mean[0]) ** 2 for v in r) // n,
           sum((v - mean[1]) ** 2 for v in g) // n,
           sum((v - mean[2]) ** 2 for v in b) // n)
    nonblack = sum(1 for i in range(n) if r[i] + g[i] + b[i] > 24) / float(n)

    # 亮区包围盒 + 逐行分布（用灰度图，省一次逐像素求和）
    gp = im.convert('L').load()
    xs, ys = [], []
    rows = []
    for y in range(H):
        cnt = 0
        for x in range(W):
            if gp[x, y] > bright_threshold:
                cnt += 1
                xs.append(x)
                ys.append(y)
        if cnt:
            rows.append((y, cnt))
    bbox = (min(xs), min(ys), max(xs), max(ys)) if xs else None

    return {
        'file': os.path.basename(path),
        'size': im.size,
        'mean': mean,
        'std': tuple(int(v ** 0.5) for v in var),
        'nonblack_pct': round(nonblack * 100, 1),
        'bright_px': len(xs),
        'bright_bbox': bbox,
        'bright_rows': rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--threshold', type=int, default=90,
                    help='判定"亮像素"的灰度阈值（默认 90）')
    ap.add_argument('--rows', action='store_true', help='打印逐行亮像素分布')
    a = ap.parse_args()

    files = frames_from_args(a.paths)
    if not files:
        print('没有匹配到任何图片', file=sys.stderr)
        return 1

    for p in files:
        s = stats(p, a.threshold)
        print('%-28s %-10s mean=%-16s std=%-14s nonblack=%5.1f%%  bright=%d  bbox=%s'
              % (s['file'], str(s['size']), str(s['mean']), str(s['std']),
                 s['nonblack_pct'], s['bright_px'], s['bright_bbox']))
        if a.rows:
            for y, c in s['bright_rows']:
                print('    y=%-5d %s' % (y, '#' * min(60, c)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
