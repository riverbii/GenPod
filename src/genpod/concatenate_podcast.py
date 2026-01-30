import argparse
from pathlib import Path

from pydub import AudioSegment


def concatenate_segments(segment_files, output_file, fade_duration=500):
    """拼接多个段落音频"""
    if not segment_files:
        print("❌ 没有音频文件可拼接")
        return
    
    print(f"🔗 正在拼接 {len(segment_files)} 个段落...")
    
    # 加载所有音频
    segments = []
    for seg_file in segment_files:
        if Path(seg_file).exists():
            segments.append(AudioSegment.from_file(seg_file))
        else:
            print(f"⚠️  警告：文件不存在 {seg_file}")
    
    if not segments:
        print("❌ 没有有效的音频文件")
        return
    
    # 拼接所有段落，段落之间添加短暂停顿（500ms）
    combined = segments[0]
    pause = AudioSegment.silent(duration=500)
    
    for seg in segments[1:]:
        combined = combined + pause + seg
    
    # 保存
    combined.export(output_file, format="wav")
    print(f"✅ 段落拼接完成: {output_file}")


def concatenate_full_podcast(dry_audio_file, welcome_file, outro_file, output_file, fade_duration=500):
    """拼接完整播客：欢迎语 + 干音 + 结束语"""
    print("🎬 正在拼接完整播客...")
    
    # 加载音频
    welcome = AudioSegment.from_file(welcome_file)
    dry = AudioSegment.from_file(dry_audio_file)
    outro = AudioSegment.from_file(outro_file)
    
    # 添加淡入淡出效果
    welcome = welcome.fade_in(fade_duration).fade_out(fade_duration)
    dry = dry.fade_in(fade_duration).fade_out(fade_duration)
    outro = outro.fade_in(fade_duration).fade_out(fade_duration)
    
    # 拼接：欢迎语 + 短暂停顿 + 干音 + 短暂停顿 + 结束语
    pause = AudioSegment.silent(duration=500)
    final = welcome + pause + dry + pause + outro
    
    # 保存
    final.export(output_file, format="wav")
    print(f"✅ 完整播客拼接完成: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="拼接播客音频"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # 拼接段落命令
    parser_segments = subparsers.add_parser('segments', help='拼接段落音频')
    parser_segments.add_argument(
        'segments',
        nargs='+',
        help='段落音频文件列表'
    )
    parser_segments.add_argument(
        '-o', '--output',
        required=True,
        help='输出文件路径'
    )
    parser_segments.add_argument(
        '--fade',
        type=int,
        default=500,
        help='淡入淡出时长（毫秒，默认：500）'
    )
    
    # 拼接完整播客命令
    parser_full = subparsers.add_parser('full', help='拼接完整播客（欢迎语+干音+结束语）')
    parser_full.add_argument(
        '--dry',
        required=True,
        help='干音文件路径'
    )
    parser_full.add_argument(
        '--welcome',
        required=True,
        help='欢迎语音频文件路径'
    )
    parser_full.add_argument(
        '--outro',
        required=True,
        help='结束语音频文件路径'
    )
    parser_full.add_argument(
        '-o', '--output',
        required=True,
        help='输出文件路径'
    )
    parser_full.add_argument(
        '--fade',
        type=int,
        default=500,
        help='淡入淡出时长（毫秒，默认：500）'
    )
    
    args = parser.parse_args()
    
    if args.command == 'segments':
        concatenate_segments(args.segments, args.output, args.fade)
    elif args.command == 'full':
        concatenate_full_podcast(
            args.dry,
            args.welcome,
            args.outro,
            args.output,
            args.fade
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
