import argparse
import logging
import multiprocessing
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import ChatTTS
import torch
import torchaudio
from pydub import AudioSegment
from pydub.silence import detect_leading_silence

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


def initialize_worker():
    """多进程 Worker 初始化：每个进程加载一次模型"""
    global _chat_instance
    if _chat_instance is None:
        _chat_instance = get_chat_instance()


def get_chat_instance():
    """获取 ChatTTS 实例（单例模式）"""
    global _chat_instance
    if _chat_instance is not None:
        return _chat_instance

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
    
    chat = ChatTTS.Chat()
    
    if local_model_exists:
        print(f"[Process {os.getpid()}] 🔄 正在加载 ChatTTS 模型（使用本地模型文件）...")
        # ChatTTS 会自动检测当前目录下的 asset 文件夹
        # 切换到项目根目录，确保能找到 asset 目录
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))
            chat.load(compile=False)  # compile=False 可以加快加载速度
            print(f"[Process {os.getpid()}] ✅ 模型加载完成（使用本地文件）")
        finally:
            os.chdir(original_cwd)
    else:
        print(f"[Process {os.getpid()}] 🔄 正在加载 ChatTTS 模型（首次运行会从网络下载模型文件）...")
        print("💡 提示：运行 download_models.sh 可以预先下载模型到本地，加快后续加载速度")
        chat.load(compile=False)  # compile=False 可以加快加载速度
        print(f"[Process {os.getpid()}] ✅ 模型加载完成")
        
    _chat_instance = chat
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


def match_target_amplitude(sound, target_dBFS):
    """Standardize loudness to target dBFS"""
    change_in_dBFS = target_dBFS - sound.dBFS
    return sound.apply_gain(change_in_dBFS)


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
    
    # 设置各库随机种子，确保极致稳定性
    import random
    import numpy as np
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    
    # 生成稳定的 speaker embedding
    # [Fix] 移除重复调用，确保逻辑唯一
    spk_emb = chat.sample_random_speaker()
    
    logger.info(f"开始生成音频 - seed: {seed}, 原始文本长度: {raw_chars} 字符, 实际文字数: {text_chars} 字")
    
    # 记录开始时间
    start_time = time.time()
    
    # --- 阶段 1: 文本归一化 (Source of Truth) ---
    # ChatTTS normalizer natively preserves [break_n] and other [tag] formats.
    normalized_text = chat.normalizer(text, do_text_normalization=True, do_homophone_replacement=True)
    logger.info(f"  normalized_text: {repr(normalized_text)}")
    logger.info("  1. 文本归一化完成")

    # --- 阶段 2: 文本润色 (Source of Prosody) ---
    logger.info("  2. 正在进行文本润色 (获取语气Tags)...")
    
    # [Optimize] 彻底剥离所有符号和换行，仅保留纯文字供模型润色。
    # 这样可以防止 [break_6] 等标签干扰模型导致其进入幻听循环。
    # 由于后续有 align_text 逻辑，标签会在推理前被自动找回。
    text_for_model = re.sub(r'\[.*?\]', '', text) # 移除所有 [tag]
    text_for_model = re.sub(r'\s+', '', text_for_model) # 移除换行和空格
    
    # 自然度优先：Refine 0.7 提供更丰富的语气起伏
    params_refine = chat.RefineTextParams(
        temperature=0.7,
        top_P=0.7,
        prompt='[laugh_0][break_4]', 
        max_new_token=1024,
        manual_seed=seed
    )
    
    refined_text_raw = chat.infer(
        [text_for_model],
        params_refine_text=params_refine,
        refine_text_only=True,
        split_text=True
    )
    
    # Handle inference result (list or string)
    if isinstance(refined_text_raw, list):
        refined_text_combined = " ".join(refined_text_raw)
    else:
        refined_text_combined = refined_text_raw

    # --- 阶段 3: 文本对齐 (Alignment) ---
    logger.info("  3. 正在执行文本对齐 (去除幻觉)...")
    from .text_aligner import align_text
    aligned_text = align_text(normalized_text, refined_text_combined)
    
    # 统计修正情况
    if aligned_text != refined_text_combined:
        diff_len = len(refined_text_combined) - len(aligned_text)
        logger.info(f"     ✅ 对齐修正完成 (差异字符数: {diff_len})")
    
    # --- 阶段 4: 音频推理 (Infer) ---
    logger.info("  4. 正在生成音频波形...")
    
    # 推理温度保持 0.3 以锁定音色，去除语速 prompt 增加自然度
    params_infer = chat.InferCodeParams(
        spk_emb=spk_emb, 
        max_new_token=2048,
        temperature=0.3, 
        top_P=0.7,
        prompt='', # 去除固定语速，让模型根据上下文自然发挥
        manual_seed=seed
    )
    
    # [Safety] Final scrub: Ensure only standard tags exist in the final string
    final_text = re.sub(r'\[\s*uv_break\s*\]', '[break_6]', aligned_text, flags=re.IGNORECASE)
    whitelisted_prefixes = ['break_', 'laugh', 'oral_', 'speed_']
    
    def tag_safety_filter(match):
        tag = match.group(0)
        inner = tag[1:-1].lower()
        if any(inner.startswith(p) for p in whitelisted_prefixes):
            return tag
        logger.warning(f"     🛡️  Safety Filter: Dropping suspicious tag {tag}")
        return ""
        
    final_text = re.sub(r'\[.*?\]', tag_safety_filter, final_text)
    
    # [Debug] Log the definitive text string
    logger.info(f"  Final Inference Text: {repr(final_text)}")
    
    # [Optimize] Disable split_text for segments shorter than 200 chars to prevent voice drift between splits
    # Also ensure no weird whitespace is triggering internal splitting
    final_text = re.sub(r'\s+', ' ', final_text).strip()
    
    wavs = chat.infer(
        [final_text], 
        use_decoder=True, 
        params_infer_code=params_infer,
        skip_refine_text=True, # Critical: Don't refine again!
        do_text_normalization=False, # It's already been normalized/refined
        split_text=True # Restore splitting for natural rhythm in longer segments
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
    
    # --- 阶段 5: 音频后处理 (Post-Processing) ---
    # 1. 自动切除前后静音
    # 2. 响度标准化 (-20 dBFS)
    try:
        sound = AudioSegment.from_wav(output_file)
        
        # 切除静音 (阈值 -50dB)
        start_trim = detect_leading_silence(sound, -50.0)
        end_trim = detect_leading_silence(sound.reverse(), -50.0)
        # 给开头留 30ms 缓冲，避免切得太死
        start_trim = max(0, start_trim - 30)
        end_trim = max(0, end_trim - 30)
        sound = sound[start_trim:len(sound)-end_trim]
        
        # 响度匹配
        normalized_sound = match_target_amplitude(sound, -20.0)
        normalized_sound.export(output_file, format="wav")
        logger.info(f"  5. 音频后处理完成 (切除静音 + -20.0 dBFS)")
    except Exception as e:
        logger.error(f"  ❌ 响度标准化失败: {e}")

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
    
    print(f"✅ 生成完毕: {output_file} ({generation_time:.2f}s, {audio_duration:.2f}s audio)")


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