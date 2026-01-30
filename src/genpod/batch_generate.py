import argparse
import logging
import multiprocessing
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加src目录到路径
# sys.path.insert(0, str(Path(__file__).parent))

from .text_processor import process_markdown_file


def setup_logging(log_file=None):
    """设置日志记录"""
    if log_file is None:
        # 默认日志文件：logs/batch_generate_YYYYMMDD.log
        # 使用当前工作目录下的 logs 目录
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"batch_generate_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def generate_segment(args_tuple):
    """生成单个段落音频（用于多进程）"""
    segment_text, segment_index, output_dir, md_dir, seed = args_tuple
    
    # 统计文字数量
    import re
    text_clean = re.sub(r'\[.*?\]', '', segment_text)
    text_clean = re.sub(r'\s+', '', text_clean)
    text_chars = len(text_clean)
    
    # md文件和wav文件分开存放
    # md文件存放在md_dir目录
    md_file = Path(md_dir) / f"segment_{segment_index:03d}.md"
    md_file.parent.mkdir(parents=True, exist_ok=True)
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(segment_text)
    
    # wav文件存放在output_dir目录
    output_file = Path(output_dir) / f"segment_{segment_index:03d}.wav"
    
    # 记录开始时间
    start_time = time.time()
    
    # 调用 generate_podcast.py
    cmd = [
        sys.executable,
        "-m", "genpod.generate_podcast",
        str(md_file),
        "-o", str(output_file),
        "-v", str(seed)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        elapsed_time = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ 段落 {segment_index} 生成完成 ({text_chars} 字, {elapsed_time:.2f}秒)")
            return (segment_index, str(output_file), text_chars, elapsed_time)
        else:
            print(f"❌ 段落 {segment_index} 生成失败: {result.stderr}")
            return None
    except Exception as e:
        print(f"❌ 段落 {segment_index} 生成出错: {e}")
        return None


def batch_generate(input_file, output_dir, seed=7470000, num_workers=None, min_chars=50, max_chars=200, logger=None):
    """并行生成多个段落音频
    
    参数：
        input_file: 输入文件路径
        output_dir: 输出目录
        seed: 随机种子
        num_workers: 并行进程数
        min_chars: 最小字数（默认50），低于此值会合并多个段落
        max_chars: 最大字数（默认200），超过此值会拆分段落
        logger: 日志记录器
    """
    if logger is None:
        logger = setup_logging()
    
    total_start_time = time.time()
    
    # 处理文本
    logger.info(f"开始处理文本文件: {input_file}")
    print("📝 正在处理文本...")
    print(f"   合并策略：最小 {min_chars} 字，最大 {max_chars} 字")
    paragraphs = process_markdown_file(input_file, min_chars, max_chars)
    print(f"✅ 文本处理完成，共 {len(paragraphs)} 个段落")
    logger.info(f"文本处理完成，共 {len(paragraphs)} 个段落")
    
    # 统计总字数
    import re
    total_chars = 0
    for i, para in enumerate(paragraphs, 1):
        text_clean = re.sub(r'\[.*?\]', '', para)
        text_clean = re.sub(r'\s+', '', text_clean)
        char_count = len(text_clean)
        total_chars += char_count
        print(f"   段落 {i}: {char_count} 字")
        logger.info(f"段落 {i:03d}: {char_count} 字")
    
    logger.info(f"总文字数: {total_chars} 字")
    
    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 创建md文件目录（与wav文件分开）
    md_dir = Path(output_dir).parent / f"{Path(output_dir).name}_md"
    md_dir.mkdir(parents=True, exist_ok=True)
    
    # 准备参数
    if num_workers is None:
        # 限制最大并行进程数为 2，避免每个进程都重新加载模型导致内存占用过高
        # 虽然总时间可能稍长，但系统资源占用更合理，每个进程的加载时间也会分散
        num_workers = min(2, len(paragraphs))
    
    args_list = [
        (para, idx, output_dir, md_dir, seed)
        for idx, para in enumerate(paragraphs, 1)
    ]
    
    # 并行生成
    logger.info(f"开始并行生成音频 - 进程数: {num_workers}, 总段落数: {len(paragraphs)}")
    print(f"🎤 开始并行生成音频（使用 {num_workers} 个进程）...")
    print("💡 提示：模型文件已下载到本地，每个进程会复用已下载的模型")
    print("💡 提示：限制并行进程数为 2，避免内存占用过高")
    
    generation_start_time = time.time()
    with multiprocessing.Pool(processes=num_workers) as pool:
        results = pool.map(generate_segment, args_list)
    generation_time = time.time() - generation_start_time
    
    # 收集成功的结果，按索引排序
    successful_results = sorted(
        [r for r in results if r is not None],
        key=lambda x: x[0]
    )
    
    # 统计信息
    total_success_chars = sum(r[2] for r in successful_results if len(r) > 2)
    total_success_time = sum(r[3] for r in successful_results if len(r) > 3)
    avg_time_per_segment = total_success_time / len(successful_results) if successful_results else 0
    avg_chars_per_segment = total_success_chars / len(successful_results) if successful_results else 0
    
    total_time = time.time() - total_start_time
    
    # 记录统计信息
    logger.info(f"批量生成完成 - 成功: {len(successful_results)}/{len(paragraphs)} 个段落")
    logger.info(f"统计信息:")
    logger.info(f"  - 总文字数: {total_success_chars} 字")
    logger.info(f"  - 总生成耗时: {generation_time:.2f} 秒")
    logger.info(f"  - 总耗时: {total_time:.2f} 秒")
    logger.info(f"  - 平均每段落耗时: {avg_time_per_segment:.2f} 秒")
    logger.info(f"  - 平均每段落字数: {avg_chars_per_segment:.1f} 字")
    logger.info(f"  - 平均生成速度: {total_success_chars/generation_time:.2f} 字/秒" if generation_time > 0 else "  - 平均生成速度: N/A")
    
    print(f"\n✅ 批量生成完成！成功生成 {len(successful_results)}/{len(paragraphs)} 个段落")
    print(f"📊 统计: {total_success_chars} 字, {generation_time:.2f}秒生成, {total_time:.2f}秒总耗时")
    print(f"📊 平均: {avg_chars_per_segment:.1f} 字/段落, {avg_time_per_segment:.2f}秒/段落")
    
    # 返回文件列表
    return [r[1] for r in successful_results]


def main():
    parser = argparse.ArgumentParser(
        description="批量并行生成播客段落音频"
    )
    
    parser.add_argument(
        'input_file',
        type=str,
        help='输入的 Markdown 文件路径'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        type=str,
        default='output/segments',
        help='输出目录（默认：output/segments）'
    )
    
    parser.add_argument(
        '-v', '--voice',
        type=str,
        default='7470000',
        help='随机种子（seed），默认：7470000'
    )
    
    parser.add_argument(
        '-j', '--jobs',
        type=int,
        default=None,
        help='并行进程数（默认：2，避免每个进程都重新加载模型导致内存占用过高）'
    )
    
    parser.add_argument(
        '--min-chars',
        type=int,
        default=50,
        help='最小字数（默认：50），低于此值会合并多个段落'
    )
    
    parser.add_argument(
        '--max-chars',
        type=int,
        default=200,
        help='最大字数（默认：200），超过此值会拆分段落'
    )
    
    parser.add_argument(
        '--log-file',
        type=str,
        default=None,
        help='日志文件路径（默认：logs/batch_generate_YYYYMMDD.log）'
    )
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.log_file)
    logger.info(f"批量生成开始 - 输入文件: {args.input_file}, 输出目录: {args.output_dir}")
    
    batch_generate(
        args.input_file,
        args.output_dir,
        seed=int(args.voice) if args.voice.isdigit() else 7470000,
        num_workers=args.jobs,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
        logger=logger
    )


if __name__ == "__main__":
    main()
