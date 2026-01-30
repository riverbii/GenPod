#!/bin/bash
# ChatTTS 模型文件下载脚本

BASE_URL="https://huggingface.co/2Noise/ChatTTS/resolve/main"
PROJECT_DIR="/Users/bixinfang/project/GenPod"

cd "$PROJECT_DIR"

# 创建目录
mkdir -p asset/gpt asset/tokenizer

echo "开始下载 ChatTTS 模型文件..."

# 下载 asset 目录下的文件
echo "下载 asset/Decoder.safetensors..."
curl -L "${BASE_URL}/asset/Decoder.safetensors" -o asset/Decoder.safetensors

echo "下载 asset/DVAE.safetensors..."
curl -L "${BASE_URL}/asset/DVAE.safetensors" -o asset/DVAE.safetensors

echo "下载 asset/Embed.safetensors..."
curl -L "${BASE_URL}/asset/Embed.safetensors" -o asset/Embed.safetensors

echo "下载 asset/Vocos.safetensors..."
curl -L "${BASE_URL}/asset/Vocos.safetensors" -o asset/Vocos.safetensors

# 下载 gpt 目录下的文件
echo "下载 asset/gpt/config.json..."
curl -L "${BASE_URL}/asset/gpt/config.json" -o asset/gpt/config.json

echo "下载 asset/gpt/model.safetensors..."
curl -L "${BASE_URL}/asset/gpt/model.safetensors" -o asset/gpt/model.safetensors

# 下载 tokenizer 目录下的文件
echo "下载 asset/tokenizer/special_tokens_map.json..."
curl -L "${BASE_URL}/asset/tokenizer/special_tokens_map.json" -o asset/tokenizer/special_tokens_map.json

echo "下载 asset/tokenizer/tokenizer_config.json..."
curl -L "${BASE_URL}/asset/tokenizer/tokenizer_config.json" -o asset/tokenizer/tokenizer_config.json

echo "下载 asset/tokenizer/tokenizer.json..."
curl -L "${BASE_URL}/asset/tokenizer/tokenizer.json" -o asset/tokenizer/tokenizer.json

echo "✅ 所有模型文件下载完成！"
