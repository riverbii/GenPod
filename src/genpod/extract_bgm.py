import argparse
from pathlib import Path

from pydub import AudioSegment


def extract_bgm_segments(bgm_file, output_dir=None, duration=5000):
    """提取BGM的前N秒和最后N秒
    
    Args:
        bgm_file: BGM文件路径
        output_dir: 输出目录（默认：BGM文件所在目录）
        duration: 提取时长（毫秒，默认5000即5秒）
    """
    bgm_path = Path(bgm_file)
    
    if not bgm_path.exists():
        print(f"❌ 错误：找不到文件 {bgm_file}")
        return
    
    # 确定输出目录
    if output_dir is None:
        output_dir = bgm_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🎵 正在加载BGM文件: {bgm_file}")
    audio = AudioSegment.from_file(str(bgm_path))
    
    total_duration = len(audio)
    print(f"📏 BGM总时长: {total_duration/1000:.2f} 秒")
    
    # 提取前N秒
    intro = audio[:duration]
    intro_file = output_dir / f"{bgm_path.stem}_intro_{duration//1000}s.mp3"
    intro.export(str(intro_file), format="mp3")
    print(f"✅ 前{duration//1000}秒已保存: {intro_file}")
    
    # 提取最后N秒
    outro = audio[-duration:]
    outro_file = output_dir / f"{bgm_path.stem}_outro_{duration//1000}s.mp3"
    outro.export(str(outro_file), format="mp3")
    print(f"✅ 最后{duration//1000}秒已保存: {outro_file}")
    
    return str(intro_file), str(outro_file)


def main():
    parser = argparse.ArgumentParser(
        description="提取BGM的前N秒和最后N秒"
    )
    
    parser.add_argument(
        'bgm_file',
        type=str,
        help='BGM文件路径'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        type=str,
        default=None,
        help='输出目录（默认：BGM文件所在目录）'
    )
    
    parser.add_argument(
        '-d', '--duration',
        type=int,
        default=5000,
        help='提取时长（毫秒，默认：5000即5秒）'
    )
    
    args = parser.parse_args()
    
    extract_bgm_segments(
        args.bgm_file,
        args.output_dir,
        args.duration
    )


if __name__ == "__main__":
    main()
