#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把截图转成 ASCII 字符画 —— 让"看不见图片"的模型能用纯文本读画面。

来源：session-4e991631，turn 1 step 30。

这是那条视觉反馈回路里最关键的一环：
    CDP 截出 PNG  →  本脚本把像素降维成字符  →  模型读字符判断
    "这一幕是不是空的 / 太挤了 / 主体偏了"  →  回去改代码  →  再截一次

用法:
    python ascii_view.py shots/_mv_shot_boot.png
    python ascii_view.py shots --cols 100 --rows 40
    python ascii_view.py shots/_mv_shot_*.png --cols 80 --rows 28

这个 MV 的画面整体很暗（背景接近纯黑），直接线性映射会几乎全是空格。
实测用 --auto-levels --gamma 0.7 才能看清主体，建议加上：

    python ascii_view.py shots --cols 96 --rows 36 --auto-levels --gamma 0.7

与原始脚本的差异:
  * 行列数改为参数（原版硬编码 96x36 和固定的 5 个场景名）。
  * 显式使用 LANCZOS 降采样（原版用默认重采样，暗部会偏暗）。
  * 新增 --auto-levels / --gamma / --invert：原版对这么暗的画面几乎看不见东西。
"""
import argparse
import glob
import os
import sys

from PIL import Image

CHARS = ' .:-=+*#%@'          # 由暗到亮


def frames_from_args(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += sorted(glob.glob(os.path.join(p, '*.png')))
        else:
            out += sorted(glob.glob(p)) or [p]
    return out


def render(path, cols, rows, invert=False, gamma=1.0, auto_levels=False):
    im = Image.open(path).convert('L').resize((cols, rows), Image.LANCZOS)
    px = im.load()

    vals = [px[x, y] for y in range(rows) for x in range(cols)]

    if auto_levels:
        lo, hi = min(vals), max(vals)
        if hi > lo:
            vals = [(v - lo) * 255 // (hi - lo) for v in vals]

    if gamma != 1.0:
        vals = [int(255 * ((v / 255.0) ** gamma)) for v in vals]

    lines = []
    for y in range(rows):
        row = []
        for x in range(cols):
            v = vals[y * cols + x]
            if invert:
                v = 255 - v
            row.append(CHARS[min(len(CHARS) - 1, v * len(CHARS) // 256)])
        lines.append(''.join(row))
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+', help='PNG 文件、通配符或目录')
    ap.add_argument('--cols', type=int, default=96)
    ap.add_argument('--rows', type=int, default=36)
    ap.add_argument('--invert', action='store_true', help='反相')
    ap.add_argument('--auto-levels', action='store_true',
                    help='按本图最暗/最亮拉伸对比度（暗场景必开）')
    ap.add_argument('--gamma', type=float, default=1.0,
                    help='<1 提亮暗部，>1 压暗；配合 --auto-levels 用 0.7 左右')
    a = ap.parse_args()

    files = frames_from_args(a.paths)
    if not files:
        print('没有匹配到任何图片', file=sys.stderr)
        return 1

    for p in files:
        name = os.path.splitext(os.path.basename(p))[0]
        print('\n==== %s ====' % name)
        for line in render(p, a.cols, a.rows, a.invert, a.gamma, a.auto_levels):
            print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
