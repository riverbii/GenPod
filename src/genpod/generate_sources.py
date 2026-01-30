import subprocess
import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from pydub import AudioSegment

from text_processor import clean_text


def generate_welcome_and_outro(seed=7470000, bgm_intro=None, bgm_outro=None):
    """生成所有欢迎词和结束语的音频，并拼接BGM片段"""
    base_dir = Path("sources")
    welcome_dir = base_dir / "welcome"
    outro_dir = base_dir / "outro"
    
    # 加载BGM片段
    bgm_intro_audio = None
    bgm_outro_audio = None
    if bgm_intro and Path(bgm_intro).exists():
        bgm_intro_audio = AudioSegment.from_file(bgm_intro)
        print(f"✅ 已加载BGM前5秒: {bgm_intro}")
    if bgm_outro and Path(bgm_outro).exists():
        bgm_outro_audio = AudioSegment.from_file(bgm_outro)
        print(f"✅ 已加载BGM后5秒: {bgm_outro}")
    
    # 生成欢迎词
    print("🎤 正在生成欢迎词...")
    for i in range(1, 6):
        # 优先使用cleaned文件，如果不存在则使用原始文件并清洗
        cleaned_file = welcome_dir / f"welcome_{i}_cleaned.md"
        md_file = welcome_dir / f"welcome_{i}.md"
        
        if cleaned_file.exists():
            temp_file = cleaned_file
        elif md_file.exists():
            # 读取并清洗文本
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            cleaned_content = clean_text(content)
            
            # 写入临时文件
            temp_file = welcome_dir / f"welcome_{i}_cleaned.md"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)
        else:
            print(f"  ⚠️  跳过 welcome_{i}：找不到源文件")
            continue
        
        # 生成音频
        output_file = welcome_dir / f"welcome_{i}.wav"
        cmd = [
            sys.executable,
            "src/generate_podcast.py",
            str(temp_file),
            "-o", str(output_file),
            "-v", str(seed)
        ]
        
        print(f"  生成 welcome_{i}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ welcome_{i} 生成完成")
            
            # 拼接BGM前5秒（音量降低一半，-6dB）
            if bgm_intro_audio:
                welcome_audio = AudioSegment.from_file(output_file)
                # BGM音量降低一半（-6dB）
                bgm_intro_low = bgm_intro_audio - 6
                # BGM前5秒 + 短暂停顿 + 欢迎词
                pause = AudioSegment.silent(duration=200)
                final_welcome = bgm_intro_low + pause + welcome_audio
                final_welcome.export(output_file, format="wav")
                print(f"  ✅ welcome_{i} 已拼接BGM前5秒（音量降低50%）")
        else:
            print(f"  ❌ welcome_{i} 生成失败: {result.stderr}")
    
    # 生成结束语
    print("\n🎤 正在生成结束语...")
    for i in range(1, 6):
        # 优先使用cleaned文件，如果不存在则使用原始文件并清洗
        cleaned_file = outro_dir / f"outro_{i}_cleaned.md"
        md_file = outro_dir / f"outro_{i}.md"
        
        if cleaned_file.exists():
            temp_file = cleaned_file
        elif md_file.exists():
            # 读取并清洗文本
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            cleaned_content = clean_text(content)
            
            # 写入临时文件
            temp_file = outro_dir / f"outro_{i}_cleaned.md"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)
        else:
            print(f"  ⚠️  跳过 outro_{i}：找不到源文件")
            continue
        
        # 生成音频
        output_file = outro_dir / f"outro_{i}.wav"
        cmd = [
            sys.executable,
            "src/generate_podcast.py",
            str(temp_file),
            "-o", str(output_file),
            "-v", str(seed)
        ]
        
        print(f"  生成 outro_{i}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ outro_{i} 生成完成")
            
            # 拼接BGM后5秒（音量降低一半，-6dB）
            if bgm_outro_audio:
                outro_audio = AudioSegment.from_file(output_file)
                # BGM音量降低一半（-6dB）
                bgm_outro_low = bgm_outro_audio - 6
                # 结束语 + 短暂停顿 + BGM后5秒
                pause = AudioSegment.silent(duration=200)
                final_outro = outro_audio + pause + bgm_outro_low
                final_outro.export(output_file, format="wav")
                print(f"  ✅ outro_{i} 已拼接BGM后5秒（音量降低50%）")
        else:
            print(f"  ❌ outro_{i} 生成失败: {result.stderr}")
    
    print("\n✅ 所有欢迎词和结束语生成完成！")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="生成欢迎词和结束语音频")
    parser.add_argument(
        '-v', '--voice',
        type=str,
        default='7470000',
        help='随机种子（seed），默认：7470000'
    )
    parser.add_argument(
        '--bgm-intro',
        type=str,
        default='sources/bgm/technology-422298_intro_5s.mp3',
        help='BGM前5秒文件路径'
    )
    parser.add_argument(
        '--bgm-outro',
        type=str,
        default='sources/bgm/technology-422298_outro_5s.mp3',
        help='BGM后5秒文件路径'
    )
    args = parser.parse_args()
    
    seed = int(args.voice) if args.voice.isdigit() else 7470000
    generate_welcome_and_outro(seed, args.bgm_intro, args.bgm_outro)
