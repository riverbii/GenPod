import argparse
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import ChatTTS
import torch
import torchaudio

from .pronunciations import DEFAULT_PRONUNCIATIONS


def setup_logging(log_file=None):
    """设置日志记录"""
    if log_file is None:
        # 默认日志文件：logs/generate_podcast_YYYYMMDD.log
        # 使用当前工作目录下的 logs 目录
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"generate_podcast_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def count_text_chars(text):
    """统计实际文字数量（去除标记和控制字符）"""
    # 移除 ChatTTS 标记：[uv_break], [laugh], [oral] 等
    text_clean = re.sub(r'\[.*?\]', '', text)
    # 移除空白字符
    text_clean = re.sub(r'\s+', '', text_clean)
    return len(text_clean)


def read_markdown_file(file_path):
    """读取 markdown 文件并提取文本内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"❌ 错误：找不到文件 {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 读取文件时出错：{e}")
        sys.exit(1)


# 全局 ChatTTS 实例（避免重复加载模型）
_chat_instance = None

def get_chat_instance():
    """获取 ChatTTS 实例（单例模式）"""
    global _chat_instance
    if _chat_instance is None:
        # 检查本地是否有模型文件
        # 优先查找当前目录下的 asset
        project_root = Path.cwd()
        asset_dir = project_root / "asset"
        local_model_exists = (
            (asset_dir / "Decoder.safetensors").exists() and
            (asset_dir / "DVAE.safetensors").exists() and
            (asset_dir / "Embed.safetensors").exists() and
            (asset_dir / "Vocos.safetensors").exists() and
            (asset_dir / "gpt" / "config.json").exists() and
            (asset_dir / "gpt" / "model.safetensors").exists() and
            (asset_dir / "tokenizer" / "tokenizer.json").exists()
        )
        
        if local_model_exists:
            print("🔄 正在加载 ChatTTS 模型（使用本地模型文件）...")
            # ChatTTS 会自动检测当前目录下的 asset 文件夹
            # 切换到项目根目录，确保能找到 asset 目录
            original_cwd = os.getcwd()
            try:
                os.chdir(str(project_root))
                _chat_instance = ChatTTS.Chat()
                _chat_instance.load(compile=False)  # compile=False 可以加快加载速度
                print("✅ 模型加载完成（使用本地文件）")
            finally:
                os.chdir(original_cwd)
        else:
            print("🔄 正在加载 ChatTTS 模型（首次运行会从网络下载模型文件）...")
            print("💡 提示：运行 download_models.sh 可以预先下载模型到本地，加快后续加载速度")
            _chat_instance = ChatTTS.Chat()
            _chat_instance.load(compile=False)  # compile=False 可以加快加载速度
            print("✅ 模型加载完成")
    return _chat_instance


def apply_pronunciations(text, dictionary):
    """Apply pronunciation replacements from dictionary (case-insensitive for keys)"""
    if not dictionary:
        return text
        
    for word, replacement in dictionary.items():
        # Use simple string replacement for now, or regex for whole words
        # Replaces all occurrences, case-insensitive logic handled by user input typically
        # But here we do simple replace to keep it predictable
        text = text.replace(str(word), str(replacement))
    return text


def generate_audio(text, voice, output_file, rate=None, pitch=None, logger=None, pronunciations=None):
    """生成音频文件（使用 ChatTTS）"""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # Check if text is empty
    if not text or not text.strip():
        logger.warning(f"Empty text for output {output_file}, skipping generation.")
        return

    # Apply pronunciation replacements
    # Merge user provided pronunciations with defaults
    # User config overrides defaults
    combined_pronunciations = DEFAULT_PRONUNCIATIONS.copy()
    if pronunciations:
        combined_pronunciations.update(pronunciations)

    # Use combined dictionary
    if combined_pronunciations:
        original_text = text
        text = apply_pronunciations(text, combined_pronunciations)
        if text != original_text:
            logger.info(f"  Applied pronunciation fixes. Text modified.")

    chat = get_chat_instance()
    
    # 统计文字数量
    text_chars = count_text_chars(text)
    raw_chars = len(text)
    
    # 将 voice 参数转换为 seed
    try:
        seed = int(voice) if voice.isdigit() else 2222
    except (ValueError, AttributeError):
        seed = 2222
    
    # ChatTTS 不支持 rate 和 pitch 参数，给出提示
    if rate or pitch:
        logger.warning("ChatTTS 不支持语速和音调调整，这些参数将被忽略")
    
    # 设置随机种子
    torch.manual_seed(seed)
    
    # 生成随机speaker embedding（用于控制音色和性别）
    spk_emb = chat.sample_random_speaker()
    
    logger.info(f"开始生成音频 - seed: {seed}, 原始文本长度: {raw_chars} 字符, 实际文字数: {text_chars} 字")
    print(f"🎤 正在生成音频（seed: {seed}）...")
    
    # 记录开始时间
    start_time = time.time()
    
    # 设置参数以避免文本被截断
    params_refine = chat.RefineTextParams(max_new_token=8192)
    params_infer = chat.InferCodeParams(spk_emb=spk_emb, max_new_token=8192)
    
    wavs = chat.infer(
        [text], 
        use_decoder=True, 
        params_refine_text=params_refine,
        params_infer_code=params_infer,
        split_text=True,
        max_split_batch=1
    )
    
    # 记录生成时间
    generation_time = time.time() - start_time
    
    # 转换为 torch tensor
    wav_array = wavs[0]
    wav_tensor = torch.from_numpy(wav_array)
    
    # 计算音频时长（秒）
    audio_duration = len(wav_array) / 24000  # 采样率 24000
    
    # 确保是 2D tensor (channels, samples)
    if len(wav_tensor.shape) == 1:
        wav_tensor = wav_tensor.unsqueeze(0)
    elif len(wav_tensor.shape) > 2:
        wav_tensor = wav_tensor[0] if wav_tensor.shape[0] == 1 else wav_tensor.squeeze()
    
    # 确保输出文件扩展名为 .wav
    output_path = Path(output_file)
    if output_path.suffix != '.wav':
        output_file = str(output_path.with_suffix('.wav'))
    
    # 保存音频（采样率 24000）
    save_start_time = time.time()
    if wav_tensor.shape[0] > wav_tensor.shape[-1]:
        wav_tensor = wav_tensor.T
    torchaudio.save(output_file, wav_tensor, 24000)
    save_time = time.time() - save_start_time
    
    total_time = time.time() - start_time
    
    # 计算速度指标
    chars_per_second = text_chars / generation_time if generation_time > 0 else 0
    audio_ratio = audio_duration / generation_time if generation_time > 0 else 0
    
    # 记录统计信息
    logger.info(f"音频生成完成 - 文件: {output_file}")
    logger.info(f"  统计信息:")
    logger.info(f"    - 原始文本长度: {raw_chars} 字符")
    logger.info(f"    - 实际文字数: {text_chars} 字")
    logger.info(f"    - 生成耗时: {generation_time:.2f} 秒")
    logger.info(f"    - 保存耗时: {save_time:.2f} 秒")
    logger.info(f"    - 总耗时: {total_time:.2f} 秒")
    logger.info(f"    - 音频时长: {audio_duration:.2f} 秒")
    logger.info(f"    - 生成速度: {chars_per_second:.2f} 字/秒")
    logger.info(f"    - 音频/生成比: {audio_ratio:.2f}x")
    
    print(f"✅ ChatTTS 生成完毕: {output_file}")
    print(f"📊 统计: {text_chars} 字, {generation_time:.2f}秒生成, {audio_duration:.2f}秒音频, {chars_per_second:.2f}字/秒")


def main():
    parser = argparse.ArgumentParser(
        description="从 Markdown 文件生成播客音频",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python generate_podcast.py script.md
  python generate_podcast.py script.md -o output.wav
  python generate_podcast.py script.md -v 2222
  python generate_podcast.py script.md -v 3333
        """
    )
    
    parser.add_argument(
        'input_file',
        type=str,
        help='输入的 Markdown 文件路径'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='输出音频文件名（默认：输入文件名.mp3）'
    )
    
    parser.add_argument(
        '-v', '--voice',
        type=str,
        default='2222',
        help='随机种子（seed），用于控制音色，默认：2222'
    )
    
    parser.add_argument(
        '-r', '--rate',
        type=str,
        default=None,
        help='语速调整（ChatTTS 不支持，将被忽略）'
    )
    
    parser.add_argument(
        '-p', '--pitch',
        type=str,
        default=None,
        help='音调调整（ChatTTS 不支持，将被忽略）'
    )
    
    parser.add_argument(
        '--log-file',
        type=str,
        default=None,
        help='日志文件路径（默认：logs/generate_podcast_YYYYMMDD.log）'
    )
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.log_file)
    logger.info(f"开始处理文件: {args.input_file}")
    
    # 读取 markdown 文件
    text = read_markdown_file(args.input_file)
    
    if not text:
        logger.error("文件内容为空")
        print("❌ 警告：文件内容为空")
        sys.exit(1)
    
    # 确定输出文件名（默认输出到 output/ 目录）
    if args.output:
        output_file = args.output
    else:
        input_path = Path(args.input_file)
        # 确保 output 目录存在
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_file = str(output_dir / (input_path.stem + ".mp3"))
    
    text_chars = count_text_chars(text)
    
    print(f"📝 读取文件: {args.input_file}")
    print(f"🎲 随机种子: {args.voice}")
    print(f"💾 输出文件: {output_file}")
    print(f"📏 文本长度: {len(text)} 字符 (实际文字: {text_chars} 字)")
    print()
    
    logger.info(f"输入文件: {args.input_file}, 输出文件: {output_file}, seed: {args.voice}")
    logger.info(f"文本统计: 原始长度 {len(text)} 字符, 实际文字数 {text_chars} 字")
    
    # 生成音频
    generate_audio(text, args.voice, output_file, args.rate, args.pitch, logger)


if __name__ == "__main__":
    main()