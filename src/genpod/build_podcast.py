#!/usr/bin/env python3
"""
一键生成播客主脚本
流程：生成干音 -> 拼接欢迎语和结束语 -> 输出最终播客
"""

import argparse
import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import edge_tts


def read_markdown_file(file_path):
    """读取 markdown 文件并提取文本内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content.strip()
    except FileNotFoundError:
        print(f"❌ 错误：找不到文件 {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 读取文件时出错：{e}")
        sys.exit(1)


async def generate_dry_audio(text, voice, output_file, rate=None, pitch=None):
    """生成干音（主内容）"""
    print(f"🎤 正在生成干音...")
    # 构建 Communicate 参数
    communicate_kwargs = {}
    if rate:
        communicate_kwargs['rate'] = rate
    if pitch:
        communicate_kwargs['pitch'] = pitch
    
    communicate = edge_tts.Communicate(text, voice, **communicate_kwargs)
    await communicate.save(output_file)
    print(f"✅ 干音生成完成: {output_file}")


def concatenate_audio_files(welcome_file, main_file, outro_file, output_file, fade_duration=500):
    """拼接音频文件"""
    from pydub import AudioSegment
    
    print(f"🔗 正在拼接音频...")
    
    try:
        welcome = AudioSegment.from_file(welcome_file)
        main_content = AudioSegment.from_file(main_file)
        outro = AudioSegment.from_file(outro_file)
    except FileNotFoundError as e:
        print(f"❌ 错误：找不到文件 {e.filename}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 加载音频文件时出错：{e}")
        sys.exit(1)
    
    # 添加淡入淡出效果
    welcome = welcome.fade_out(fade_duration)
    main_content = main_content.fade_in(fade_duration).fade_out(fade_duration)
    outro = outro.fade_in(fade_duration)
    
    # 拼接
    final_audio = welcome + main_content + outro
    final_audio.export(output_file, format="mp3")
    
    total_duration = len(final_audio) / 1000
    print(f"✅ 音频拼接完成: {output_file}")
    print(f"📊 总时长: {total_duration:.2f} 秒")


def find_audio_file(directory, default_name=None):
    """在目录中查找音频文件"""
    dir_path = Path(directory)
    if not dir_path.exists():
        return None
    
    # 如果指定了默认文件名，优先查找
    if default_name:
        default_path = dir_path / default_name
        if default_path.exists():
            return str(default_path)
    
    # 查找目录中的第一个音频文件
    audio_extensions = ['.mp3', '.wav', '.m4a', '.flac']
    for ext in audio_extensions:
        files = list(dir_path.glob(f'*{ext}'))
        if files:
            return str(files[0])
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description="一键生成播客：从 Markdown 脚本生成完整播客",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 使用默认文件名（基于日期）
  python build_podcast.py input/script.md
  
  # 指定输入文件
  python build_podcast.py input/2026-01-27.md
  
  # 指定欢迎语和结束语文件
  python build_podcast.py input/script.md --welcome sources/welcome/welcome.mp3 --outro sources/outro/outro.mp3
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
        help='最终输出文件名（默认：output/YYYY-MM-DD_podcast.mp3）'
    )
    
    parser.add_argument(
        '-v', '--voice',
        type=str,
        default='zh-CN-XiaoxiaoNeural',
        help='语音模型（默认：zh-CN-XiaoxiaoNeural）'
    )
    
    parser.add_argument(
        '-r', '--rate',
        type=str,
        default=None,
        help='语速调整（例如：+20%%, -10%%, 默认：不调整）'
    )
    
    parser.add_argument(
        '-p', '--pitch',
        type=str,
        default=None,
        help='音调调整（例如：+2Hz, -1Hz, 默认：不调整）'
    )
    
    parser.add_argument(
        '--welcome',
        type=str,
        default=None,
        help='欢迎语音频文件路径（默认：自动查找 sources/welcome/）'
    )
    
    parser.add_argument(
        '--outro',
        type=str,
        default=None,
        help='结束语音频文件路径（默认：自动查找 sources/outro/）'
    )
    
    parser.add_argument(
        '--fade',
        type=int,
        default=500,
        help='音频之间的淡入淡出时长（毫秒，默认：500）'
    )
    
    parser.add_argument(
        '--keep-dry',
        action='store_true',
        help='保留干音文件（默认：不保留）'
    )
    
    args = parser.parse_args()
    
    # 读取 markdown 文件
    input_path = Path(args.input_file)
    text = read_markdown_file(args.input_file)
    
    if not text:
        print("❌ 警告：文件内容为空")
        sys.exit(1)
    
    # 确定日期（用于文件名）
    try:
        # 尝试从文件名提取日期（格式：YYYY-MM-DD.md）
        date_str = input_path.stem
        if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
            date = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            date = datetime.now()
    except:
        date = datetime.now()
    
    date_str = date.strftime('%Y-%m-%d')
    
    # 确保目录存在
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # 确定文件路径
    dry_audio_file = str(output_dir / f"{date_str}_dry.mp3")
    
    if args.output:
        final_output_file = args.output
    else:
        final_output_file = str(output_dir / f"{date_str}_podcast.mp3")
    
    # 查找欢迎语和结束语文件
    welcome_file = args.welcome
    if not welcome_file:
        welcome_file = find_audio_file("sources/welcome")
        if not welcome_file:
            print("❌ 错误：找不到欢迎语音频文件")
            print("   请将欢迎语音频放入 sources/welcome/ 目录，或使用 --welcome 参数指定")
            sys.exit(1)
    
    outro_file = args.outro
    if not outro_file:
        outro_file = find_audio_file("sources/outro")
        if not outro_file:
            print("❌ 错误：找不到结束语音频文件")
            print("   请将结束语音频放入 sources/outro/ 目录，或使用 --outro 参数指定")
            sys.exit(1)
    
    # 打印信息
    print("=" * 60)
    print("🎙️  播客一键生成工具")
    print("=" * 60)
    print(f"📝 输入文件: {args.input_file}")
    print(f"🎤 语音模型: {args.voice}")
    if args.rate:
        print(f"⚡ 语速: {args.rate}")
    if args.pitch:
        print(f"🎵 音调: {args.pitch}")
    print(f"👋 欢迎语: {welcome_file}")
    print(f"👋 结束语: {outro_file}")
    print(f"💾 干音输出: {dry_audio_file}")
    print(f"💾 最终输出: {final_output_file}")
    print(f"📏 文本长度: {len(text)} 字符")
    print()
    
    # 步骤 1: 生成干音
    print("📌 步骤 1/2: 生成干音")
    print("-" * 60)
    asyncio.run(generate_dry_audio(text, args.voice, dry_audio_file, args.rate, args.pitch))
    print()
    
    # 步骤 2: 拼接音频
    print("📌 步骤 2/2: 拼接音频")
    print("-" * 60)
    concatenate_audio_files(
        welcome_file,
        dry_audio_file,
        outro_file,
        final_output_file,
        args.fade
    )
    print()
    
    # 清理临时文件
    if not args.keep_dry:
        print("🧹 清理临时文件...")
        Path(dry_audio_file).unlink()
        print(f"   已删除: {dry_audio_file}")
    
    print()
    print("=" * 60)
    print(f"✨ 播客生成完成！")
    print(f"📁 最终文件: {final_output_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
