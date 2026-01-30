import argparse
import sys
import logging
from pathlib import Path
import hashlib
import json
try:
    import tomllib
except ImportError:
    import tomli as tomllib

from .text_processor import process_markdown_file

# Lazy imports
# from .generate_podcast import generate_audio
# from .concatenate_podcast import concatenate_segments, concatenate_full_podcast

# Setup logging
def setup_logging(verbose=False):
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format=log_format, handlers=[logging.StreamHandler(sys.stdout)])
    return logging.getLogger(__name__)

logger = logging.getLogger(__name__)

def load_config(input_dir):
    """
    Load config with precedence: 
    1. Episode config (input_dir/genpod.toml)
    2. Local config (./genpod.toml)
    3. Global config (~/.genpod.toml)
    4. Defaults
    """
    # 4. Defaults
    config = {
        "voice_seed": 2222,
        "min_chars": 50,
        "max_chars": 200,
        "welcome_audio": None,
        "outro_bgm": None,
        "fade_duration": 500
    }
    
    # helper to merge config
    def merge_from_file(path, name):
        if path.exists():
            try:
                with open(path, "rb") as f:
                    user_config = tomllib.load(f)
                    config.update(user_config)
                    logger.info(f"Loaded {name} config from {path}")
            except Exception as e:
                logger.warning(f"Failed to load {name} config from {path}: {e}")

    # 3. Global Configuration (~/.genpod.toml)
    global_config = Path.home() / ".genpod.toml"
    merge_from_file(global_config, "global")
    
    # 2. Local Configuration (./genpod.toml) - only if different from input_dir
    local_config = Path.cwd() / "genpod.toml"
    # Ensure we don't load the same file twice if input_dir is current dir
    if local_config.resolve() != (input_dir / "genpod.toml").resolve():
        merge_from_file(local_config, "local")

    # 1. Episode Configuration (input_dir/genpod.toml)
    episode_config = input_dir / "genpod.toml"
    merge_from_file(episode_config, "episode")
            
    return config

def compute_hash(text, seed):
    """Compute SHA256 hash of text + seed to identify unique segments"""
    content = f"{text}{seed}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]

def build_podcast(input_name, output_dir_str=None, workdir=None, verbose=False, force=False):
    """Build the full podcast from input name or directory"""
    logger = setup_logging(verbose)
    
    # Path resolution logic
    if workdir:
        workdir_path = Path(workdir).resolve()
        input_dir = workdir_path / "input" / input_name
        if not output_dir_str:
            output_base = workdir_path / "output"
        else:
            output_base = Path(output_dir_str).resolve()
    else:
        # Backwards compatibility: treat input_name as a direct path
        input_dir = Path(input_name).resolve()
        if not output_dir_str:
            # Default to project project-root/output
            output_base = Path.cwd() / "output"
        else:
            output_base = Path(output_dir_str).resolve()

    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)
        
    output_dir = output_base / input_dir.name
    segments_dir = output_base / f"{input_dir.name}_segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Building podcast for {input_dir.name}")
    logger.info(f"Input: {input_dir}")
    logger.info(f"Output: {output_dir}")
    
    # Load config
    config = load_config(input_dir)
    seed = config["voice_seed"]
    
    # 1. Process Script
    script_path = input_dir / "script.md"
    if not script_path.exists():
        logger.error(f"script.md not found in {input_dir}")
        sys.exit(1)
        
    paragraphs = process_markdown_file(
        str(script_path), 
        min_chars=config["min_chars"], 
        max_chars=config["max_chars"]
    )
    logger.info(f"Parsed {len(paragraphs)} paragraphs from script.md")
    
    # 2. Incremental Generation
    segment_files = []
    
    # Lazy import to speed up 'check' command
    from .generate_podcast import generate_audio
    
    for i, text in enumerate(paragraphs, 1):
        # Hash text + seed to get unique ID
        seg_hash = compute_hash(text, seed)
        audio_filename_hash_only = f"segment_{seg_hash}.wav"
        audio_path_hash_only = segments_dir / audio_filename_hash_only
        
        if audio_path_hash_only.exists() and not force:
            logger.info(f"[Skip] Segment {i} (Hash: {seg_hash}) already exists")
        else:
            logger.info(f"[Gen ] Generating Segment {i} (Hash: {seg_hash}, {len(text)} chars)...")
            # Generate
            generate_audio(text, str(seed), str(audio_path_hash_only), logger=logger)
            
        segment_files.append(str(audio_path_hash_only))
        
    # 3. Concatenate Segments (Dry)
    # The order is strictly preserved by the order of paragraphs in the script
    from .concatenate_podcast import concatenate_segments, concatenate_full_podcast
    dry_file = output_base / f"{input_dir.name}_dry.wav"
    concatenate_segments(segment_files, str(dry_file), fade_duration=config["fade_duration"])
    
    # 4. Final Mix (Full)
    final_file = output_base / f"{input_dir.name}_final.wav"
    
    # Resolve assets
    # Welcome
    welcome_file = config["welcome_audio"]
    # Outro
    outro_file = config["outro_bgm"]
    
    # If assets provided, do full mix
    if welcome_file and outro_file:
        logger.info(f"Creating final mix with welcome={welcome_file}, outro={outro_file}")
        concatenate_full_podcast(
            str(dry_file), 
            welcome_file, 
            outro_file, 
            str(final_file), 
            fade_duration=config["fade_duration"]
        )
        
    logger.info(f"Build complete!")
    logger.info(f"  Final: {final_file if (welcome_file and outro_file) else 'N/A'}")
    logger.info(f"  Dry:   {dry_file}")
    logger.info(f"  Segments: {segments_dir}")

def check_script(input_name, workdir=None, verbose=False):
    """Check script segmentation without generating audio"""
    logger = setup_logging(verbose)
    
    if workdir:
        input_dir = Path(workdir).resolve() / "input" / input_name
    else:
        input_dir = Path(input_name).resolve()
    
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)
        
    # Load config
    config = load_config(input_dir)
    
    # Process Script
    script_path = input_dir / "script.md"
    if not script_path.exists():
        logger.error(f"script.md not found in {input_dir}")
        sys.exit(1)
        
    paragraphs = process_markdown_file(
        str(script_path), 
        min_chars=config["min_chars"], 
        max_chars=config["max_chars"]
    )
    
    print(f"\n🔍 Checking segmentation for: {script_path}")
    print(f"   Config: min_chars={config['min_chars']}, max_chars={config['max_chars']}")
    print(f"   Total Paragraphs: {len(paragraphs)}\n")
    
    for i, text in enumerate(paragraphs, 1):
        # Preview first 50 chars
        preview = text.replace('\n', ' ')[:50] + "..."
        word_count = len(text)
        print(f"   [{i:03d}] {word_count} chars | {preview}")
        
    print("\n✅ Check complete. Use 'genpod build' to generate.")

def main():
    parser = argparse.ArgumentParser(description="GenPod CLI Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Build Command
    build_parser = subparsers.add_parser("build", help="Build podcast from input directory")
    build_parser.add_argument("input", help="Path to input directory or episode name")
    build_parser.add_argument("-w", "--workdir", help="Base workspace directory")
    build_parser.add_argument("-o", "--output", help="Output directory root")
    build_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    build_parser.add_argument("-f", "--force", action="store_true", help="Force regenerate all segments")
    
    # Check Command
    check_parser = subparsers.add_parser("check", help="Check script segmentation")
    check_parser.add_argument("input", help="Path to input directory or episode name")
    check_parser.add_argument("-w", "--workdir", help="Base workspace directory")
    check_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.command == "build":
        build_podcast(args.input, args.output, args.workdir, args.verbose, args.force)
    elif args.command == "check":
        check_script(args.input, args.workdir, args.verbose)



if __name__ == "__main__":
    main()
