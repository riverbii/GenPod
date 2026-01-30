# GenPod - 播客音频生成工具

一个基于 ChatTTS 和 pydub 的播客音频生成和混音工具，支持一键生成完整播客。

## ✨ 特性

- 🎙️ **一键生成播客**：从 Markdown 脚本自动生成完整播客
- 🎤 **ChatTTS 语音合成**：使用 ChatTTS 生成自然流畅的中文语音
- 📝 **智能文本处理**：自动数字转中文、智能分段、过滤 Markdown 元数据
- 🔗 **自动拼接**：自动拼接欢迎语、主内容和 BGM 结尾
- 🎵 **音频处理**：支持淡入淡出、音量调整、BGM 混音等效果
- ⚡ **批量生成**：支持多进程并行生成段落音频，提高效率
- 📁 **结构化输入**：支持按日期组织播客内容（title.md, script.md, shownotes.md）

## 📁 项目结构

```
GenPod/
├── src/                           # 源代码目录
│   ├── batch_generate.py          # ⭐ 批量生成段落音频（推荐）
│   ├── generate_podcast.py        # 从 Markdown 生成单个音频
│   ├── concatenate_podcast.py     # 拼接音频工具（段落/完整播客）
│   ├── mix_podcast.py             # 混音工具（人声 + BGM）
│   ├── text_processor.py          # 文本处理（数字转换、分段等）
│   ├── build_podcast.py           # 一键生成播客（旧版，已弃用）
│   └── generate_sources.py        # 生成欢迎语/结束语音频
├── input/                         # 输入的 Markdown 文本文件
│   └── YYYYMMDD/                  # 按日期组织的播客内容
│       ├── title.md                # 播客标题
│       ├── script.md               # 播客脚本（主内容）
│       └── shownotes.md            # 播客说明
├── output/                        # 生成的音频输出文件
│   └── YYYYMMDD_segments/         # 段落音频文件
│   └── YYYYMMDD_segments_md/      # 段落 Markdown 文件
│   └── YYYYMMDD_dry.wav           # 拼接后的干音
│   └── YYYYMMDD_final.wav         # 最终播客文件
├── sources/                       # 音源文件
│   ├── welcome/                   # 欢迎语音频文件（.wav 和 .md）
│   │   ├── welcome_1.wav
│   │   └── welcome_1_cleaned.md
│   ├── outro/                     # 结束语音频文件（.wav 和 .md）
│   │   ├── outro_1.wav
│   │   └── outro_1_cleaned.md
│   └── bgm/                       # 背景音乐文件
│       ├── technology-422298.mp3
│       ├── technology-422298_intro_5s.mp3
│       └── technology-422298_outro_5s.mp3
├── seed_config.txt                # 默认 seed 配置（7470000）
└── README.md
```

## 🚀 快速开始

### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install chattts torch torchaudio soundfile pydub numpy

# macOS 安装 ffmpeg（用于 pydub）
brew install ffmpeg
```

**注意：** 首次运行 ChatTTS 会自动下载约 1GB 的模型文件，需要联网。如果下载失败，可以手动下载模型文件到项目目录。

### 2. 准备音源文件

将欢迎语和结束语的音频文件放入对应目录：

```bash
# 欢迎语音频放入 sources/welcome/
# 结束语音频放入 sources/outro/
# BGM 文件放入 sources/bgm/
```

### 3. 创建播客内容

在 `input/` 目录下创建日期目录和文件：

```bash
# 创建日期目录
mkdir -p input/20260129

# 创建脚本文件
vim input/20260129/script.md
```

### 4. 生成播客

```bash
# 批量生成段落音频（自动分段）
uv run python src/batch_generate.py input/20260129/script.md \
  -o output/20260129_segments \
  -v 7470000

# 拼接所有段落生成干音
uv run python src/concatenate_podcast.py segments \
  $(ls output/20260129_segments/segment_*.wav | sort -V) \
  -o output/20260129_dry.wav

# 拼接完整播客（欢迎语 + 干音 + BGM结尾）
uv run python src/concatenate_podcast.py full \
  --dry output/20260129_dry.wav \
  --welcome sources/welcome/welcome_1.wav \
  --outro sources/bgm/technology-422298_outro_5s.mp3 \
  -o output/20260129_final.wav
```

完成！播客文件会保存在 `output/20260129_final.wav`

## 📖 详细使用说明

### ⭐ 批量生成段落音频（推荐）

**主要工作流程**：从 Markdown 脚本自动分段并生成音频

```bash
# Basic usage (using default seed)
genpod-batch input/20260129/script.md \
  -o output/20260129_segments

# Specify random seed (control voice)
genpod-batch input/20260129/script.md \
  -o output/20260129_segments \
  -v 7470000

# Custom parameters (min/max chars)
genpod-batch input/20260129/script.md \
  -o output/20260129_segments \
  --min-chars 50 \
  --max-chars 200
```

**工作流程：**
1. 读取 Markdown 文件
2. 过滤 Markdown 元数据（标题、TTS 设置建议等）
3. 文本处理（数字转中文、逗号改句号、每句一行）
4. 按段落拆分
5. 智能合并段落（控制每段字数在 min_chars 和 max_chars 之间）
6. 多进程并行生成每个段落的音频
7. 保存段落 Markdown 文件到 `*_segments_md/` 目录
8. 保存段落音频文件到 `*_segments/` 目录

**默认参数：**
- 最小字数（min_chars）：50
- 最大字数（max_chars）：200
- 随机种子（seed）：从 `seed_config.txt` 读取（默认 7470000）

### 文本处理功能

`text_processor.py` 提供以下功能：

1. **数字转中文**：
   - 自动将阿拉伯数字转换为中文读法
   - 支持年份（如 2026 → 二零二六）
   - 支持单位（如 25万 → 二十五万）

2. **文本清洗**：
   - 逗号改句号
   - 每句一行
   - 去掉所有空格

3. **智能分段**：
   - 按段落拆分（双换行符）
   - 智能合并短段落
   - 自动拆分超长段落
   - 保持每段字数在合理范围内

4. **Markdown 过滤**：
   - 移除标题行（以 `#` 开头）
   - 移除 TTS 设置建议部分
   - 移除加粗标记

### 生成单个音频

从单个 Markdown 文件生成音频：

```bash
# 基本用法（使用默认 seed）
uv run python src/generate_podcast.py input/script.md

# 指定输出文件名
uv run python src/generate_podcast.py input/script.md \
  -o output/my_podcast.wav

# 使用不同的随机种子（控制音色）
uv run python src/generate_podcast.py input/script.md \
  -v 7470000
```

**默认参数：**
- 随机种子（seed）：从 `seed_config.txt` 读取（默认 7470000）
- 输出格式：WAV（采样率 24000Hz）

**关于随机种子：**
- 不同的 seed 值会产生不同的音色
- seed 值存储在 `seed_config.txt` 文件中
- 找到喜欢的音色后，更新 `seed_config.txt` 文件即可

**注意事项：**
- ChatTTS 不支持语速和音调调整（`-r` 和 `-p` 参数会被忽略）
- 输出格式为 WAV，不是 MP3
- 首次运行需要下载模型文件（约 1GB），需要联网

### 拼接音频

#### 拼接段落

将多个段落音频文件拼接成干音：

```bash
uv run python src/concatenate_podcast.py segments \
  output/20260129_segments/segment_001.wav \
  output/20260129_segments/segment_002.wav \
  output/20260129_segments/segment_003.wav \
  -o output/20260129_dry.wav

# 或使用通配符
uv run python src/concatenate_podcast.py segments \
  $(ls output/20260129_segments/segment_*.wav | sort -V) \
  -o output/20260129_dry.wav
```

#### 拼接完整播客

拼接欢迎语、干音和 BGM 结尾：

```bash
uv run python src/concatenate_podcast.py full \
  --dry output/20260129_dry.wav \
  --welcome sources/welcome/welcome_1.wav \
  --outro sources/bgm/technology-422298_outro_5s.mp3 \
  -o output/20260129_final.wav
```

**参数说明：**
- `--dry`: 干音文件路径（必需）
- `--welcome`: 欢迎语音频文件路径（必需）
- `--outro`: 结尾音频文件路径（必需，可以是 BGM 或结束语）
- `-o, --output`: 输出文件路径（必需）
- `--fade`: 淡入淡出时长（毫秒，默认：500）

### 混音处理（添加背景音乐）

将人声音频与背景音乐混合：

```bash
# 基本用法
uv run python src/mix_podcast.py output/voice.wav sources/bgm/bgm.mp3

# 指定输出文件名
uv run python src/mix_podcast.py output/voice.wav sources/bgm/bgm.mp3 \
  -o output/final.wav

# 自定义开头和结尾时长
uv run python src/mix_podcast.py output/voice.wav sources/bgm/bgm.mp3 \
  --intro 3000 --outro 5000

# 调整 BGM 音量降低值
uv run python src/mix_podcast.py output/voice.wav sources/bgm/bgm.mp3 \
  --bgm-volume 20
```

**混音参数说明：**
- `--intro`: 开头音乐独奏时长（毫秒，默认：2000）
- `--outro`: 结尾音乐独奏时长（毫秒，默认：3000）
- `--bgm-volume`: BGM 音量降低值（dB，默认：18）

## 📝 日常使用流程

每天只需要三步：

1. **创建播客内容**：在 `input/` 目录创建日期目录和文件
   ```bash
   mkdir -p input/20260129
   vim input/20260129/script.md
   ```

2. **生成段落音频**：批量生成所有段落
   ```bash
   uv run python src/batch_generate.py input/20260129/script.md \
     -o output/20260129_segments
   ```

3. **拼接完整播客**：拼接所有段落和音源
   ```bash
   # 拼接段落
   uv run python src/concatenate_podcast.py segments \
     $(ls output/20260129_segments/segment_*.wav | sort -V) \
     -o output/20260129_dry.wav
   
   # 拼接完整播客
   uv run python src/concatenate_podcast.py full \
     --dry output/20260129_dry.wav \
     --welcome sources/welcome/welcome_1.wav \
     --outro sources/bgm/technology-422298_outro_5s.mp3 \
     -o output/20260129_final.wav
   ```

完成！最终播客文件在 `output/20260129_final.wav`

## 🎵 支持的音频格式

- **输入**：MP3, WAV, M4A, FLAC 等（pydub 支持的格式）
- **输出**：
  - `generate_podcast.py`：WAV（ChatTTS 生成）
  - `concatenate_podcast.py`：WAV（拼接后的播客）

## 📌 注意事项

- 确保 `output/`、`sources/welcome/`、`sources/outro/` 和 `sources/bgm/` 目录存在
- 段落 Markdown 文件和音频文件分开存放：
  - Markdown 文件：`output/YYYYMMDD_segments_md/`
  - 音频文件：`output/YYYYMMDD_segments/`
- 默认 seed 值存储在 `seed_config.txt` 文件中（默认：7470000）
- 文本处理会自动过滤 Markdown 元数据，无需手动清理
- 分段功能会自动控制每段字数在 50-200 之间
- ChatTTS 首次运行需要下载模型文件，确保网络连接正常
- 如果遇到模型下载失败，可以手动下载模型文件到项目目录

## 🔧 生成欢迎语和结束语

如果需要重新生成欢迎语或结束语的音频：

```bash
# 生成单个欢迎语（使用 seed 7470000）
uv run python src/generate_podcast.py \
  sources/welcome/welcome_1_cleaned.md \
  -o sources/welcome/welcome_1.wav \
  -v 7470000

# 生成单个结束语
uv run python src/generate_podcast.py \
  sources/outro/outro_1_cleaned.md \
  -o sources/outro/outro_1.wav \
  -v 7470000
```

**提示：** 生成的 WAV 文件可以直接使用，无需转换为其他格式。

## 📚 相关资源

- [ChatTTS 文档](https://github.com/2noise/ChatTTS)
- [pydub 文档](https://github.com/jiaaro/pydub)

## 📄 许可证

MIT License
