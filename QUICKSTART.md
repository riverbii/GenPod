# 🚀 快速开始指南

## 第一次使用

### 1. 安装依赖

```bash
pip install edge-tts pydub

# macOS 安装 ffmpeg
brew install ffmpeg
```

### 2. 准备音源文件

将你的欢迎语和结束语音频文件放入对应目录：

```bash
# 欢迎语（例如："欢迎收听小河早报..."）
cp your_welcome.mp3 sources/welcome/

# 结束语（例如："感谢收听，我们下期再见..."）
cp your_outro.mp3 sources/outro/
```

### 3. 创建脚本文件

在 `input/` 目录下创建当天的脚本文件，建议使用日期命名：

```bash
# 创建今天的脚本
touch input/2026-01-27.md

# 编辑内容
vim input/2026-01-27.md
```

### 4. 一键生成播客

```bash
python src/build_podcast.py input/2026-01-27.md
```

完成！最终播客文件会保存在 `output/2026-01-27_podcast.mp3`

## 日常使用流程

每天只需要：

1. **创建脚本**：在 `input/` 目录创建 `YYYY-MM-DD.md` 文件
2. **编写内容**：编辑脚本内容
3. **一键生成**：运行 `python src/build_podcast.py input/YYYY-MM-DD.md`

就这么简单！

## 常见问题

**Q: 欢迎语和结束语文件找不到？**
A: 确保文件已放入 `sources/welcome/` 和 `sources/outro/` 目录，或使用 `--welcome` 和 `--outro` 参数指定路径。

**Q: 如何保留干音文件用于调试？**
A: 使用 `--keep-dry` 参数，干音文件会保存在 `output/` 目录。

**Q: 如何自定义输出文件名？**
A: 使用 `-o` 参数：`python src/build_podcast.py input/script.md -o output/my_podcast.mp3`

**Q: 如何更换语音模型？**
A: 使用 `-v` 参数：`python src/build_podcast.py input/script.md -v zh-CN-YunxiNeural`
