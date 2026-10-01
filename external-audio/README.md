# external-audio/ — 外链音频版

从仓库根目录的单文件版本拆出来的「精简 HTML + 独立音频」。

| 文件 | 大小 | 说明 |
|---|---|---|
| `world.execute(me)-MV.html` | 68 KB | 同样的动画，音频改为相对路径引用 |
| `audio.mp3` | 8.1 MB | 从 HTML 内嵌数据里拆出来的音频 |

音频与根目录版本内嵌的那份**逐字节一致**：
SHA256 `C74A281648794565B5A85C9472FFE343ACFA824BC9068C733B464A533341744D`。

单文件版 11.4 MB 里有 11.37 MB 是这段 base64，拆开后 HTML 只剩 **0.62%**，
便于阅读、diff 和编辑。**两个文件必须放在同一目录。**

## ⚠️ `file://` 下会丢掉卡点（已自动降级，但有声音）

浏览器的安全策略：从 `file://` 打开时，外部音频文件被当作跨源媒体。
此时 `createMediaElementSource()` **不抛异常**，但频谱恒为 0、输出静音 ——
也就是「看起来一切正常，其实没声音、卡点也不动」。

实测对比（同一台机器、同一首曲子）：

| 载入方式 | audioCtx | analyser | bassLevel | 频谱和 | 节拍来源 |
|---|---|---|---|---|---|
| 根目录单文件（内嵌 data URI） | created | created | 0.687 | 5114 | 真实频谱 ✅ |
| 外链 + `file://`，**无守卫**（修复前的状态） | created | created | **0** | **0** | ❌ 静音 |
| 外链 + `file://`，有守卫（**本目录当前的状态**） | null | null | 0 | — | 回退 128 BPM ✅ |
| 外链 + `http://` | created | created | **0.688** | **4863** | 真实频谱 ✅ |

因此拆出来的这份 HTML 在 `initAudioGraph()` 里注入了一段守卫（源码里有
`[split_audio.py 注入]` 标注）：识别到「外链音频 + `file://`」就跳过 Web Audio，
让 `<audio>` 走原生播放路径 —— **保证有声音**，节拍检测自动回退到固定 128 BPM。

## 想要完整的卡点同步：用本地服务器打开

```bash
cd external-audio
python -m http.server 8000
```

然后浏览器访问 `http://127.0.0.1:8000/world.execute(me)-MV.html`。

实测 `http://` 下 bassLevel 0.688 / 频谱和 4863，与内嵌版本（0.687 / 5114）
基本一致，卡点完全恢复。根目录的单文件版本不受这个问题影响 —— 它用内嵌
data URI，不存在跨源，双击即播且卡点正常。

## 生成 / 还原

本目录由 `tools/split_audio.py` 生成：

```bash
python tools/split_audio.py "world.execute(me)-MV.html" --out-dir external-audio
```

反向操作（重新合成单文件）用 `tools/build_html.py`，但注意它认的是这一行：

```js
const AUDIO_SRC = "data:audio/mpeg;base64,__AUDIO_BASE64__";
```

而本目录的 HTML 已经被换成相对路径引用，所以想还原成单文件，要先把那一行改回
占位符形式，再执行 `build_html.py --template ... --audio audio.mp3 --out ...`。

这个往返已验证过：把根目录成品的 data URI 换回占位符当模板，再用
`build_html.py` 重新注入 `audio.mp3`，产物与根目录成品 **SHA256 完全相同**
（`FD000BDA4FC7D6D98BADC05128E689472ADA68F8A419CBA2983833B4883D2803`）。

## 版权

同仓库根目录的 `README.md`。
