# world.execute(me); — Canvas MV

Mili《world.execute (me) ;》的单文件 HTML 动画 MV。**一个 `.html` 文件，双击即播**：无服务器、无外部依赖、无构建步骤、完全离线。

## 文件

| 文件 | 大小 | 说明 |
|---|---|---|
| `world.execute(me)-MV.html` | 10.92 MB | 成品。MP3 以 base64 内嵌，**双击即播、离线可用** |
| `external-audio/` | 8.2 MB | 同一动画的拆解版：精简 HTML（68 KB）+ 独立 `audio.mp3`，便于阅读和编辑 |
| `tools/` | ~37 KB | 生成时用到的辅助脚本，共 10 个文件 |
| `session.v4.jsonl` | 1.68 MB | 生成过程的事件日志（DeepSeek Harness 会话记录） |

内嵌音频校验：SHA256 `C74A281648794565B5A85C9472FFE343ACFA824BC9068C733B464A533341744D`，8,531,525 字节，与源 `Mili - world.execute (me) ;.mp3` **逐字节一致**。

## 作者评价

> 这是个人认为 DeepSeek 做得最好的一版，之后都没能复刻出这么完美的，疑似灰测思维链？

## 生成信息

以下均取自 `session.v4.jsonl` 的原始记录，而非事后回忆：

- **模型**：`deepseek-v4-pro`（provider `deepseek-account`），reasoning effort 由 `high` 提升至 `max`
- **形态**：**一条用户消息 → 单轮自治任务**（turn 1）；无子代理（`delegationDepth: 0`、`agentPreset: minimal`）
- **规模**：44 个 step、43 次工具调用（42 次 `pwsh` + 1 次环境查询）
- **耗时**：turn 1 约 **17 分钟**；turn 2 在约 29 小时后只用了 2 步做文件一致性验证

### 关键：它给自己搭了一个「看得见」的回路

这是这一版效果明显更好的核心原因。turn 1 的 42 次 `pwsh` 调用大致分成四段：

1. **手工解析 MP3**（step 3–6）
   环境里没有 `ffmpeg` / `ffprobe`，模型直接用 Python `struct` 手写了一个 **MP3 帧解析器**来算出歌曲时长。

2. **分段产出 HTML**（step 7–13）
   把 HTML 拆成 5 段，用 PowerShell here-string 分别写盘，音频位置留 `__AUDIO_BASE64__` 占位符，最后再拼入 base64 data URI —— **避免让 11 MB 的 base64 走一遍模型上下文**，并在结尾校验占位符已被替换。

3. **自建视觉反馈回路**（step 14–28）
   找到 Edge，以 `--remote-debugging-port=9334` 启动，用 Node 通过 **CDP over WebSocket** 驱动浏览器并截图。

4. **「看」截图**（step 29–37）
   用 PIL 把截图的像素转成 **ASCII art 字符画**，以纯文本形式「看到」画面，再据此迭代。

最后做 SHA256 与占位符完整性校验。

> 值得注意：模型本身看不了图片。它是把自己渲染出的帧**降维成 ASCII 字符画再读回来**，用这种方式绕开了「看不见自己输出」的限制 —— 而这个限制，正是同类任务质量不稳定的主因之一。

### 原始提示词

```text
@"C:\Users\ASUS\Desktop\Mili - world.execute (me) ;.mp3" @"C:\Users\ASUS\Desktop\Mili - world.execute (me) ;.lrc" 帮我做一个world.execute(me)的MV，歌曲已经给你，你需要使用html来实现，画面风格你自己来定，选择一个你觉得最合适的就行，需要完整的HTML动画，在HTML里连续播放，要求:
1:要有不同的场景切换，不要为了切换场景而硬做场景。
2:中间不能有明显卡顿，掉帧。要结合歌曲的卡点。
3:可以先上网搜索你的热门形象来辅助构建，可以适当使用颜文字。
3.5:适当加入一些你喜欢的元素
4:这次工作你不能使用任何的skil,可以调用agentteam，但是模型只能使用deepseekv4.1flash，不能使用其他的模型。
```

## 技术栈

全部为浏览器原生能力，无任何框架或第三方库。

| 层 | 实现 |
|---|---|
| 渲染 | HTML5 **Canvas 2D** 立即模式绘制（`getContext('2d', {alpha:false, desynchronized:true})`），**非 WebGL** |
| 音频 | `new Audio(dataURI)`，MP3 以 `data:audio/mpeg;base64` 内联，单文件自包含 |
| 音频分析 | `AudioContext` → `createMediaElementSource` → `AnalyserNode`（`fftSize=256`，`smoothingTimeConstant=0.75`） |
| 时间轴 | `audio.currentTime` 作为**唯一主时钟**，实现音画同步 |
| 主循环 | `requestAnimationFrame`，`dt` 上限 0.05 s |
| 节拍检测 | 取频谱第 1–27 个 bin（跳过 DC 分量）求低频能量，43 帧滑动均值 + 自适应阈值（`avg*1.42+0.025`、`>0.09`、间隔 >245 ms）；无 `AnalyserNode` 时降级为 128 BPM 固定节拍 |
| 场景系统 | 14 幕 `SCENES` 时间轴 + 1.25 s 重叠转场（alpha 混合 / `clip()` 遮罩 iris·heart·wipe / flash·glitch 强调层） |
| 性能优化 | 离屏 canvas 精灵缓存（发光·emoji·文字·歌词）、`createPattern` 平铺扫描线与噪点、静态几何预计算、DPR ≤ 1.5、半分辨率渐晕贴图 |
| 确定性随机 | `hash(n) = fract(sin(n*127.1 + 311.7) * 43758.5453)` 用于所有位置分布，保证每帧稳定 |
| 歌词 | 内嵌 LRC，正则解析时间戳，大写单词高亮为粉色 |
| 交互 | 点击启动（绕过自动播放限制）、Space 暂停、F / 双击全屏、M 静音 |

### 14 幕场景

```
启动终端 → 编译世界 → 几何情书 → 电流隧道 → 神经核心/心形网络 → 可爱数据花园
→ 双极身份 → 碎裂孤立 → 非法参数报错 → EXECUTION 脉冲 → 重建 → 爱的方程 → 星轨 → 关机
```

## tools/ — 生成时用到的辅助脚本

`tools/` 里是从 `session.v4.jsonl` 中抽出来的工装脚本，也就是模型当时为自己搭的
那条 **「渲染 → 观察 → 修改」闭环**：量出歌曲时长、分段拼 HTML 并注入音频、用 CDP
驱动无头浏览器逐幕截图、再把截图转成 ASCII 字符画读回来。

最值得一看的是 `ascii_view.py` —— 模型看不了图片，于是用字符画把画面降维成自己
能读的文本。**这大概就是这一版效果好于同类尝试的主要原因**：它是「看见」了再改，
而不是盲写。

| 文件 | 作用 |
|---|---|
| `mp3_duration.py` | 纯 Python 解析 MP3 时长，不依赖 ffmpeg / ffprobe / mutagen |
| `build_html.py` | 拼接分段 HTML，把 MP3 以 base64 注入占位符（避免 11 MB 走模型上下文） |
| `split_audio.py` | `build_html.py` 的逆操作：把内嵌音频拆成「外链音频 + 精简 HTML」 |
| `launch_edge.ps1` | 启动 headless Edge/Chrome 并开启 DevTools Protocol |
| `cdp_probe.js` | CDP 体检：时长、浮层状态、canvas 分辨率、JS 异常 |
| `cdp_capture.js` | 定位到指定时间点逐幕截图 |
| `ascii_view.py` | 截图 → ASCII 字符画 |
| `image_stats.py` | 亮度统计、非黑像素占比、亮区包围盒 |
| `verify_html.ps1` | 成品完整性校验（占位符 / 数据 URI / 结构 / SHA256） |

详见 [`tools/README.md`](tools/README.md)。

## 声明

**本仓库由 `deepseek-flash` 上传。**

| 环节 | 执行者 |
|---|---|
| MV 生成（`world.execute(me)-MV.html`） | `deepseek-v4-pro` —— 会话 `session-4e991631` |
| 仓库创建与上传、`tools/` 抽取与验证、`.gitattributes`、技术栈核对 | `deepseek-flash` |

注意区分：**作品是 `deepseek-v4-pro` 生成的**（见上文「生成信息」，有会话日志为证）；
`deepseek-flash` 负责的是把它归档到这里，并把生成过程中用到的工装脚本提取、修正、
跑通后一并入库。

## 版权声明

歌曲《world.execute (me) ;》的版权归 Mili 及相应权利方所有。本仓库为个人技术存档，内嵌完整音频仅为让单个 HTML 文件离线可播，不作任何商业用途。如权利人提出异议，将立即删除相关文件。
