import argparse
import sys
from pathlib import Path

from pydub import AudioSegment


def mix_podcast(voice_file, bgm_file, output_file, intro_duration=2000, outro_duration=3000, bgm_volume_reduction=18):
    """
    混音播客：将人声音频与背景音乐混合
    
    Args:
        voice_file: 人声音频文件路径
        bgm_file: 背景音乐文件路径
        output_file: 输出文件路径
        intro_duration: 开头音乐独奏时长（毫秒）
        outro_duration: 结尾音乐独奏时长（毫秒）
        bgm_volume_reduction: BGM 音量降低值（dB）
    """
    print("🎚️ 正在进行混音处理...")

    # 1. 加载音频文件
    try:
        voice = AudioSegment.from_file(voice_file)
        bgm = AudioSegment.from_file(bgm_file)
    except FileNotFoundError as e:
        print(f"❌ 错误：找不到文件 {e.filename}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 加载音频文件时出错：{e}")
        sys.exit(1)

    # 2. 调整背景音乐 (BGM)
    # 策略：降低 BGM 音量，以免盖过人声
    bgm_low = bgm - bgm_volume_reduction
    
    # 3. 计算需要的时长
    # 我们希望：开头音乐独奏 + 人声时长 + 结尾音乐独奏
    total_duration = intro_duration + len(voice) + outro_duration

    # 4. 循环 BGM (如果 BGM 比人声短，就循环播放)
    combined_bgm = bgm_low
    while len(combined_bgm) < total_duration:
        combined_bgm += bgm_low  # 拼接

    # 5. 裁剪 BGM 到确切长度
    final_bgm = combined_bgm[:total_duration]

    # 6. 制作"淡入"和"淡出"效果
    # 开头淡入，结尾淡出，听起来更丝滑
    final_bgm = final_bgm.fade_in(intro_duration).fade_out(outro_duration)

    # 7. 合成 (Overlay)
    # 把人声叠加在 BGM 上，position 参数决定人声从第几毫秒开始
    podcast = final_bgm.overlay(voice, position=intro_duration)

    # 8. 导出
    podcast.export(output_file, format="mp3")
    print(f"✨ 播客制作完成！已保存为: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="混音播客：将人声音频与背景音乐混合",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python mix_podcast.py voice.mp3 bgm.mp3
  python mix_podcast.py voice.mp3 bgm.mp3 -o final.mp3
  python mix_podcast.py voice.mp3 bgm.mp3 --intro 3000 --outro 5000
        """
    )
    
    parser.add_argument(
        'voice_file',
        type=str,
        help='人声音频文件路径'
    )
    
    parser.add_argument(
        'bgm_file',
        type=str,
        help='背景音乐文件路径'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='输出文件路径（默认：output/final_podcast.mp3）'
    )
    
    parser.add_argument(
        '--intro',
        type=int,
        default=2000,
        help='开头音乐独奏时长（毫秒，默认：2000）'
    )
    
    parser.add_argument(
        '--outro',
        type=int,
        default=3000,
        help='结尾音乐独奏时长（毫秒，默认：3000）'
    )
    
    parser.add_argument(
        '--bgm-volume',
        type=int,
        default=18,
        help='BGM 音量降低值（dB，默认：18）'
    )
    
    args = parser.parse_args()
    
    # 确定输出文件路径（默认输出到 output/ 目录）
    if args.output:
        output_file = args.output
    else:
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_file = str(output_dir / "final_podcast.mp3")
    
    print(f"🎤 人声文件: {args.voice_file}")
    print(f"🎵 BGM 文件: {args.bgm_file}")
    print(f"💾 输出文件: {output_file}")
    print(f"⏱️  开头时长: {args.intro}ms, 结尾时长: {args.outro}ms")
    print()
    
    # 执行混音
    mix_podcast(
        args.voice_file,
        args.bgm_file,
        output_file,
        args.intro,
        args.outro,
        args.bgm_volume
    )


if __name__ == "__main__":
    main()
