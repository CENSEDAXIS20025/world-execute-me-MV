# tools/ — 从那次会话里抽出来的工装

这里放的不是 MV 的一部分，而是**生成这个 MV 时模型给自己造的辅助脚本**。
除 `split_audio.py` 是本次新增（逆操作，见文件清单）外，其余全部来自
`session.v4.jsonl`（`session-4e991631`，模型 `deepseek-v4-pro`）。

## 为什么值得留存

那次生成的效果明显好于后来的尝试，关键不在提示词，而在于模型**自己搭了一条
「渲染 → 观察 → 修改」的闭环**：

```
手工量出歌曲时长            mp3_duration.py
        ↓
分段写 HTML + 注入音频      build_html.py
        ↓
无头浏览器 + 开 CDP          launch_edge.ps1
        ↓
逐幕截图                    cdp_capture.js
        ↓
把截图降维成文本「看」        ascii_view.py / image_stats.py
        ↓
不满意 → 回去改 → 再截一次
        ↓
成品完整性校验               verify_html.ps1
```

模型本身看不了图片。它用 **ASCII 字符画**把画面变成自己能读的文本 ——
**这就是它"能看见自己输出"的办法**，也正是同类任务质量不稳定的根本原因所在：
大多数生成过程是盲写的。

## 文件清单

| 文件 | 来源步骤 | 作用 |
|---|---|---|
| `mp3_duration.py` | step 5–6 | 纯 Python 解析 MP3 时长，不依赖 ffmpeg / ffprobe / mutagen |
| `build_html.py` | step 13, 17, 20 | 拼接分段 HTML；把 MP3 以 base64 注入占位符（避免 11 MB 走模型上下文）；可注入静音 WAV 做快速调试 |
| `split_audio.py` | 新增 | `build_html.py` 的逆操作：把内嵌音频拆成「外链音频 + 精简 HTML」，并注入 `file://` 的 Web Audio 守卫 |
| `launch_edge.ps1` | step 14, 21 | 启动 headless Edge/Chrome，开启 `--remote-debugging-port` |
| `cdp_probe.js` | step 24, 27 | CDP 体检：时长是否解出、浮层状态、canvas 分辨率、JS 异常与控制台报错 |
| `cdp_capture.js` | step 28 | 把音频定位到指定时间点，逐幕截图 |
| `ascii_view.py` | step 30 | 截图 → ASCII 字符画 |
| `image_stats.py` | step 29, 33 | 亮度统计、非黑像素占比、亮区包围盒、逐行分布 |
| `verify_html.ps1` | step 39, 40 | 成品校验：占位符/数据 URI/结构/SHA256 |

## 跑一遍完整回路

```powershell
# 0) 先量出歌曲时长（用来校准时间轴）
python tools\mp3_duration.py "song.mp3"

# 1) 起浏览器，拿到 CDP 的 webSocketDebuggerUrl
powershell -File tools\launch_edge.ps1 -HtmlPath "D:\path\world.execute(me)-MV.html"

# 2) 先体检，确认页面本身没坏
node tools\cdp_probe.js --url world.execute

# 3) 逐幕截图
node tools\cdp_capture.js --url world.execute --out .\shots

# 4) 用文本「看」画面
#    这个 MV 画面很暗，不加 --auto-levels 几乎全是空格，看不出东西
python tools\ascii_view.py .\shots --cols 96 --rows 36 --auto-levels --gamma 0.7

# 5) 用指标找异常（全黑 / 出界 / 过曝）
python tools\image_stats.py .\shots --rows

# 6) 校验成品
powershell -File tools\verify_html.ps1 -Path "D:\path\world.execute(me)-MV.html"
```

依赖：Python 3 + Pillow，**Node 22 或更新**，以及任意 Chromium 内核浏览器。
**不需要 puppeteer / playwright。**

> Node 版本要求说明：`cdp_*.js` 用的是内置 `fetch` 和**全局 `WebSocket`**。
> `fetch` 从 Node 18 起就有，但按 Node 官方文档，全局 `WebSocket` 是
> *Added in: v21.0.0, v20.10.0*，且在 v22.0.0 之前需要
> `--experimental-websocket` 开关、v22.4.0 才转为稳定。所以这里要求 22+。

## 三点说明

1. **平台**：`launch_edge.ps1` 与 `verify_html.ps1` 是 Windows PowerShell 脚本
   （依赖 Edge/Chrome 的默认安装路径和 `Start-Process`）。Node / Python 那几个
   是跨平台的。
2. **所有 `.ps1` 都是纯 ASCII**，这不是偷懒。Windows PowerShell 5.1 会用系统
   ANSI 代码页解析没有 BOM 的 `.ps1` 文件，中文注释会导致解析失败 —— 这个坑
   在本次工作中真实踩到过。`.py` / `.js` 不受此限制。
3. **对原始脚本做了少量改动**，均写在各文件头部：路径改为命令行参数；
   `mp3_duration.py` 修正了 Layer I / III 的帧长分支（原版两处错误恰好互相
   抵消，总时长仍然正确，但逐帧游走是错位的）；`ascii_view.py` 改用 LANCZOS
   降采样并新增 `--auto-levels` / `--gamma`。其余逻辑保持原样。

已验证：`build_html.py` 做了往返测试 —— 把根目录成品的 data URI 换回占位符当模板，
再用 `--audio` 重新注入，产物与根目录成品 **SHA256 完全相同**（`FD000BDA…`）。

## 版权

同仓库根目录的 `README.md`。
