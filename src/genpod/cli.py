import argparse
import sys
import logging
import xml.sax.saxutils as saxutils
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
        "fade_duration": 500,
        # RSS / Channel Metadata
        "podcast_title": "My Awesome Podcast",
        "podcast_description": "A podcast about cool things.",
        "podcast_link": "https://example.com",
        "podcast_language": "zh-cn",
        "podcast_author": "Author Name",
        "podcast_email": "hello@example.com",
        "podcast_image": "https://example.com/cover.jpg",
        "podcast_category": "Technology",
        "podcast_copyright": "2026 Author",
        "podcast_audio_url_prefix": None  # Defaults to podcast_link/audio if None
    }
    
    # helper to merge config
    def merge_from_file(path, name):
        if path.exists():
            try:
                with open(path, "rb") as f:
                    user_config = tomllib.load(f)
                    config.update(user_config)
                    logger.info(f"Loaded {name} config from {path}. Keys: {list(user_config.keys())}")
                    if "welcome_audio" in user_config:
                         logger.info(f"  -> welcome_audio: {user_config['welcome_audio']}")
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
    # Path resolution logic
    if workdir:
        workdir_path = Path(workdir).resolve()
        
        # Check if input_name is an existing path (absolute or relative to cwd)
        direct_path = Path(input_name).resolve()
        if direct_path.exists():
             input_path = direct_path
        else:
             input_path = workdir_path / "input" / input_name
             
        if not output_dir_str:
            output_base = workdir_path / "output"
        else:
            output_base = Path(output_dir_str).resolve()
    else:
        # Backwards compatibility: treat input_name as a direct path
        input_path = Path(input_name).resolve()
        if not output_dir_str:
            # Default to project project-root/output
            output_base = Path.cwd() / "output"
        else:
            output_base = Path(output_dir_str).resolve()

    # Check if input is a segments_md directory
    is_file_mode = input_path.is_file() and input_path.suffix == ".md"
    is_segments_dir_mode = input_path.is_dir() and input_path.name.endswith("_segments_md")

    if is_file_mode:
        # File mode: treat the file as script.md OR a segment file
        input_dir = input_path.parent
        script_filename = input_path.name
        
        # [Fix]: Smart detection of episode name from directory structure
        if "_segments_md" in input_dir.name:
             episode_name = input_dir.name.replace("_segments_md", "")
        else:
             episode_name = input_path.stem
             
        script_path = input_path
        
    elif is_segments_dir_mode:
        # [NEW MODE]: Batch process all segments in the directory
        input_dir = input_path.parent # Parent of segments_md usually? or just input_path
        # If input is workspace/output/20260131/20260131_segments_md
        # episode name is 20260131
        episode_name = input_path.name.replace("_segments_md", "")
        # script_path is irrelevant here
        script_path = input_path # Placeholder
        
    else:
        # Directory mode: expect script.md inside
        input_dir = input_path
        script_filename = "script.md"
        episode_name = input_dir.name
        script_path = input_dir / "script.md"

    if not input_path.exists():
        logger.error(f"Input not found: {input_path}")
        sys.exit(1)
        
    output_dir = output_base / episode_name
    output_dir.mkdir(parents=True, exist_ok=True)
    segments_dir = output_dir / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Building podcast for {episode_name}")
    logger.info(f"Input: {input_path}")
    logger.info(f"Output: {output_dir}")
    
    # Load config 
    # Try finding config in standard places
    config_path = Path.cwd() / "genpod.toml"
    config = load_config(input_dir if not is_file_mode else Path.cwd())
    seed = config["voice_seed"]
    
    is_segment_file = is_file_mode and input_path.name.startswith("segment_")
    
    if is_segment_file:
         # [Targeted Regeneration] If input is a segment file, don't split it!
         with open(script_path, "r", encoding="utf-8") as f:
             content = f.read().strip()
         paragraphs = [content] 
         logger.info(f"Targeted Build: {input_path.name}")
         
    elif is_segments_dir_mode:
        # [Batch Regeneration] Load all .md files, sorted
        logger.info(f"Batch Build from Segment Directory: {input_path}")
        md_files = sorted(list(input_path.glob("segment_*.md")))
        if not md_files:
             logger.error("No segment files found in directory!")
             sys.exit(1)
             
        paragraphs = []
        for mf in md_files:
            with open(mf, "r", encoding="utf-8") as f:
                paragraphs.append(f.read().strip())
        
        logger.info(f"Loaded {len(paragraphs)} segments directly from files.")
        
    else:
        # Normal Full Build
        if not script_path.exists():
            logger.error(f"Script file not found: {script_path}")
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
    
    # [CRITICAL FIX] If input is already a segment file, skip md creation entirely
    if is_segment_file:
        # Direct audio generation mode - no md file management
        for i, text in enumerate(paragraphs, 1):
            seg_hash = compute_hash(text, seed)
            audio_filename = f"segment_{seg_hash}.wav"
            audio_path = segments_dir / audio_filename
            
            logger.info(f"[Gen ] Generating audio for {input_path.name} (Hash: {seg_hash})...")
            generate_audio(
                text, 
                str(seed), 
                str(audio_path), 
                logger=logger,
                pronunciations=config.get("pronunciation", {})
            )
            segment_files.append(str(audio_path))
            
    elif is_segments_dir_mode:
        # Batch mode - just iterate and generate
        for i, text in enumerate(paragraphs, 1):
             # Simple naming
             audio_filename = f"segment_{i:03d}.wav"
             audio_path = segments_dir / audio_filename
             
             if audio_path.exists() and not force:
                 logger.info(f"[Skip] Segment {i} already exists")
             else:
                 logger.info(f"[Gen ] Generating Segment {i}...")
                 generate_audio(
                    text, 
                    str(seed), 
                    str(audio_path), 
                    logger=logger,
                    pronunciations=config.get("pronunciation", {})
                 )
             segment_files.append(str(audio_path))
            
    else:
        # Normal mode: manage md files
        segments_md_dir = output_dir / "segments_md"
        segments_md_dir.mkdir(parents=True, exist_ok=True)
        
        for i, text in enumerate(paragraphs, 1):
            # [Workflow logic]: Check if user has manually edited this segment file
            existing_segment_files = list(segments_md_dir.glob(f"segment_{i:03d}_*.md"))
            
            if existing_segment_files:
                # Use the existing file as source of truth
                target_file = existing_segment_files[0]
                with open(target_file, "r", encoding="utf-8") as f:
                    text = f.read().strip()
            
            # Hash text + seed to get unique ID (for cache checking)
            seg_hash = compute_hash(text, seed)
            
            # Save washed segment to file for user verification
            segment_md_file = segments_md_dir / f"segment_{i:03d}_{seg_hash}.md"
            
            if not segment_md_file.exists():
                with open(segment_md_file, "w", encoding="utf-8") as f:
                    f.write(text)
            
            # Use simple sequence-based naming for audio files
            audio_filename = f"segment_{i:03d}.wav"
            audio_path = segments_dir / audio_filename
        
            if audio_path.exists() and not force:
                logger.info(f"[Skip] Segment {i} already exists")
            else:
                logger.info(f"[Gen ] Generating Segment {i} ({len(text)} chars)...")
                # Generate
                generate_audio(
                    text, 
                    str(seed), 
                    str(audio_path), 
                    logger=logger,
                    pronunciations=config.get("pronunciation", {})
                )
            
            segment_files.append(str(audio_path))
        
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
    logger.info(f"Config Check - Welcome: {welcome_file}, Outro: {outro_file}")
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
    
    # Create directory for washed markdown segments for inspection
    input_base = input_dir.parent
    # Assuming standard structure workspace/input/DATE, output should be workspace/output/DATE
    # But check_script logic for path resolution is a bit different, let's try to infer output dir 
    # taking into account workdir if present, or just use input_dir logic
    
    # Re-using build_podcast logic for consistency:
    # If using workdir workspace/ -> output is workspace/output/DATE
    if workdir:
        output_base = Path(workdir).resolve() / "output"
    else:
        # Fallback: create output folder next to input folder
        output_base = input_dir.parent.parent / "output"
        if not output_base.exists():
             output_base = Path.cwd() / "output"

    episode_name = input_dir.name
    segments_md_dir = output_base / episode_name / f"{episode_name}_segments_md"
    segments_md_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Saving debug segments to: {segments_md_dir}")
    seed = config["voice_seed"]

    for i, text in enumerate(paragraphs, 1):
        # Hash text + seed
        seg_hash = compute_hash(text, seed)
        
        # Save washed segment
        segment_md_file = segments_md_dir / f"segment_{i:03d}_{seg_hash}.md"
        with open(segment_md_file, "w", encoding="utf-8") as f:
            f.write(text)

        # Preview first 50 chars
        preview = text.replace('\n', ' ')[:50] + "..."
        word_count = len(text)
        print(f"   [{i:03d}] {word_count} chars | {preview}")
        print(f"         -> Saved: {segment_md_file.name}")
        
    print(f"\n✅ Check complete. Segments saved to {segments_md_dir}")
    print("Use 'genpod build' to generate audio.")

def get_template_path(name):
    """Get path to a template file"""
    # Look for templates in the package
    template_dir = Path(__file__).parent / "templates"
    return template_dir / name

def init_project(project_name):
    """Initialize a new GenPod project structure"""
    root = Path(project_name).resolve()
    if root.exists():
        print(f"❌ Error: Directory '{project_name}' already exists.")
        sys.exit(1)
        
    dirs = [
        "assets/bgm",
        "assets/welcome",
        "assets/outro",
        "episodes",
        "docs/rss",
        "docs/audio",
        "docs/images",
        "scripts",
        "workspace/input",
        "workspace/output"
    ]
    
    print(f"🚀 Initializing GenPod project: {project_name}")
    root.mkdir(parents=True)
    
    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)
        print(f"  Created: {d}/")
        
    # Copy default genpod.toml from templates
    template_path = get_template_path("genpod.toml")
    target_path = root / "genpod.toml"
    
    if template_path.exists():
        import shutil
        shutil.copy(template_path, target_path)
        print("  Created: genpod.toml (from template)")
    else:
        # Fallback if template missing
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("# GenPod Configuration\nvoice_seed = 2222\n")
        print("  Created: genpod.toml (fallback)")
    
    print(f"\n✅ Project '{project_name}' initialized successfully!")

def manage_config(init=False):
    """Manage configuration files"""
    if init:
        target_path = Path.cwd() / "genpod.toml"
        if target_path.exists():
            print(f"❌ Error: 'genpod.toml' already exists in current directory.")
            sys.exit(1)
            
        template_path = get_template_path("genpod.toml")
        if template_path.exists():
            import shutil
            shutil.copy(template_path, target_path)
            print(f"✅ Created 'genpod.toml' in {Path.cwd()}")
        else:
            print(f"❌ Error: Template not found at {template_path}")
            sys.exit(1)

def generate_rss(project_dir):
    """Generate RSS feed from episodes directory"""
    root = Path(project_dir).resolve()
    episodes_dir = root / "episodes"
    # Try docs/rss first, fall back to website/rss (legacy)
    rss_file = root / "docs" / "rss" / "feed.xml"
    if not (root / "docs").exists() and (root / "website").exists():
        rss_file = root / "website" / "rss" / "feed.xml"
    
    # Ensure parent dir exists
    rss_file.parent.mkdir(parents=True, exist_ok=True)
    
    if not episodes_dir.exists():
        print(f"❌ Error: 'episodes' directory not found in {root}")
        sys.exit(1)
        
    config = load_config(root)
    audio_url_prefix = config.get("podcast_audio_url_prefix") or f"{config['podcast_link']}/audio"
    
    items_xml = []
    
    # Scan episodes (directories)
    episode_dirs = sorted([d for d in episodes_dir.iterdir() if d.is_dir()], reverse=True)
    
    print(f"🔍 Scanning {len(episode_dirs)} episodes for RSS...")
    
    for ep_dir in episode_dirs:
        # Find audio file (*_final.wav/mp3 or any wav/mp3)
        audio_exts = ["*_final.wav", "*_final.mp3", "*.wav", "*.mp3"]
        audio_files = []
        for ext in audio_exts:
            audio_files = list(ep_dir.glob(ext))
            if audio_files: break
            
        if not audio_files:
            continue
            
        audio_path = audio_files[0]
        ep_id = ep_dir.name
        
        # MIME Type
        mime_type = "audio/wav" if audio_path.suffix.lower() == ".wav" else "audio/mpeg"
        
        # Metadata extraction
        # Title
        title = ep_id
        title_file = ep_dir / "title.md"
        if not title_file.exists(): title_file = ep_dir / f"{ep_id}_title.md"
        
        if title_file.exists():
            with open(title_file, "r", encoding="utf-8") as f:
                title = f.read().strip()
                
        # Description / Shownotes
        description = ""
        summary = ""
        shownotes_file = ep_dir / "shownotes.md"
        if not shownotes_file.exists(): shownotes_file = ep_dir / f"{ep_id}_shownotes.md"
        
        if shownotes_file.exists():
            with open(shownotes_file, "r", encoding="utf-8") as f:
                description = f.read().strip()
                summary = description[:500] if len(description) > 500 else description
        else:
            # Fallback to script preview
            script_file = ep_dir / "script.md"
            if not script_file.exists(): script_file = ep_dir / f"{ep_id}_script.md"
            if script_file.exists():
                with open(script_file, "r", encoding="utf-8") as f:
                    script_text = f.read().strip()
                    description = script_text[:200] + "..." if len(script_text) > 200 else script_text
                    summary = description
                    
        # Episode Image
        ep_image = ""
        for img_name in ["cover.jpg", "cover.png", "image.jpg", "image.png"]:
            img_path = ep_dir / img_name
            if img_path.exists():
                # Assuming images are hosted in an 'images' dir relative to podcast_link
                ep_image = f'\n      <itunes:image href="{config["podcast_link"]}/images/{ep_id}/{img_name}" />'
                break

        # File info
        file_size = audio_path.stat().st_size
        # Duration (using pydub if possible)
        duration_sec = 0
        try:
            from pydub.utils import mediainfo
            info = mediainfo(str(audio_path))
            duration_sec = int(float(info.get('duration', 0)))
        except:
            # Simple fallback if possible (very rough approx for wav)
            if audio_path.suffix.lower() == ".wav":
                # WAV: samples = file_size / (channels * bytes_per_sample)
                # approx duration = file_size / (24000 * 2) = 48000 bytes/sec at 24k mono 16bit?
                pass
            
        # PubDate (approximation or from filename if YYYYMMDD)
        import datetime
        pub_date = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")
        if ep_id.isdigit() and len(ep_id) == 8:
            try:
                date_obj = datetime.datetime.strptime(ep_id, "%Y%m%d")
                pub_date = date_obj.strftime("%a, %d %b %Y 08:00:00 +0800")
            except: pass
            
        # Escape XML entities for non-CDATA fields
        safe_title = saxutils.escape(title)
        safe_summary = saxutils.escape(summary)
        
        item = f"""    <item>
      <title>{safe_title}</title>
      <itunes:title>{safe_title}</itunes:title>
      <itunes:author>{saxutils.escape(config['podcast_author'])}</itunes:author>
      <description><![CDATA[{description}]]></description>
      <itunes:summary>{safe_summary}</itunes:summary>
      <pubDate> {pub_date}</pubDate>
      <enclosure url="{audio_url_prefix}/{audio_path.name}" length="{file_size}" type="{mime_type}" />
      <guid isPermaLink="false">{ep_id}</guid>
      <itunes:duration>{duration_sec}</itunes:duration>
      <itunes:episodeType>full</itunes:episodeType>{ep_image}
    </item>"""
        items_xml.append(item)
        print(f"  Added: {title}")

    items_joined = "\n".join(items_xml)
    rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" 
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" 
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{saxutils.escape(config['podcast_title'])}</title>
    <link>{saxutils.escape(config['podcast_link'])}</link>
    <language>{saxutils.escape(config['podcast_language'])}</language>
    <copyright>{saxutils.escape(config['podcast_copyright'])}</copyright>
    <itunes:author>{saxutils.escape(config['podcast_author'])}</itunes:author>
    <description>{saxutils.escape(config['podcast_description'])}</description>
    <itunes:type>episodic</itunes:type>
    <itunes:owner>
      <itunes:name>{saxutils.escape(config['podcast_author'])}</itunes:name>
      <itunes:email>{saxutils.escape(config['podcast_email'])}</itunes:email>
    </itunes:owner>
    <itunes:image href="{saxutils.escape(config['podcast_image'])}" />
    <itunes:category text="{saxutils.escape(config['podcast_category'])}" />
    <itunes:explicit>false</itunes:explicit>

{items_joined}
  </channel>
</rss>
"""
    rss_file.parent.mkdir(parents=True, exist_ok=True)
    with open(rss_file, "w", encoding="utf-8") as f:
        f.write(rss_content)
    print(f"\n✅ RSS feed generated: {rss_file}")

def audition_voices(output_dir=".", count=5, text=None, workdir=None):
    """Generate audio samples with random seeds"""
    import random
    
    # Setup paths
    if workdir:
        base_dir = Path(workdir).resolve()
    else:
        base_dir = Path(output_dir).resolve()
        
    audition_dir = base_dir / "workspace" / "audition"
    audition_dir.mkdir(parents=True, exist_ok=True)
    
    logger = setup_logging(verbose=True)
    
    # Lazy import
    from .generate_podcast import generate_audio
    
    print(f"🎤 Auditioning {count} voices...")
    print(f"📂 Output: {audition_dir}\n")
    
    # Known good seeds (optional mix of random and curated)
    # For now, purely random integers between 1 and 9999
    seeds = [random.randint(1, 9999) for _ in range(count)]
    
    for i, seed in enumerate(seeds, 1):
        if text:
            sample_text = text
        else:
            sample_text = f"你好，我是{seed}号播音员。这是一个测试音频，用于测试我的音色是否符合您的要求。"
            
        filename = f"seed_{seed}.wav"
        output_path = audition_dir / filename
        
        print(f"[{i}/{count}] Generating seed {seed}...")
        try:
            generate_audio(sample_text, str(seed), str(output_path), logger=logger)
            print(f"  ✅ Saved: {filename}")
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            
    print(f"\n✨ Audition complete! Check the files in: {audition_dir}")

def merge_segments(episode_name, workdir=None, output_file=None):
    """Merge segment contents back into a single script file"""
    import re
    if workdir:
        base_dir = Path(workdir).resolve()
        segments_dir = base_dir / "output" / episode_name / f"{episode_name}_segments_md"
    else:
        # Try to guess
        base_dir = Path.cwd()
        segments_dir = base_dir / f"{episode_name}_segments_md"
        
    if not segments_dir.exists():
        print(f"❌ Error: Segments directory not found: {segments_dir}")
        sys.exit(1)
        
    print(f"🔍 Merging segments from: {segments_dir}")
    
    # Sort files by segment index (segment_001_...)
    files = sorted(list(segments_dir.glob("segment_*.md")))
    if not files:
        print("❌ No segment files found.")
        sys.exit(1)
        
    full_text = ""
    for f in files:
        with open(f, "r", encoding="utf-8") as fs:
            full_text += fs.read().strip() + "\n\n"
            
    # Output path
    if output_file:
        out_path = Path(output_file).resolve()
    else:
        # Default to episodes/DATE/script.md
        # Assuming standard structure if workdir is provided
        if workdir:
             out_path = Path(workdir).resolve().parent / "episodes" / episode_name / f"{episode_name}_script.md"
             if not out_path.parent.exists():
                 # Fallback to local
                 out_path = Path.cwd() / f"{episode_name}_merged.md"
        else:
            out_path = Path.cwd() / f"{episode_name}_merged.md"
            
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_text.strip())
        
    print(f"✅ Merged {len(files)} segments into: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="GenPod CLI Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # BUILD Command
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

    # Init Command
    init_parser = subparsers.add_parser("init", help="Initialize a new podcast project")
    init_parser.add_argument("name", help="Project name (directory)")

    # Config Command
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument("--init", action="store_true", help="Initialize a genpod.toml in current directory")

    # RSS Command
    rss_parser = subparsers.add_parser("rss", help="Generate RSS feed")
    rss_parser.add_argument("project_dir", nargs="?", default=".", help="Project root directory")
    
    # Audition Command
    audition_parser = subparsers.add_parser("audition", help="Generate random voice samples")
    audition_parser.add_argument("-n", "--count", type=int, default=5, help="Number of samples (default: 5)")
    audition_parser.add_argument("-t", "--text", help="Custom text for audition")
    audition_parser.add_argument("-w", "--workdir", help="Base workspace directory")

    # Merge Command
    merge_parser = subparsers.add_parser("merge", help="Merge segments back to script")
    merge_parser.add_argument("episode", help="Episode name (e.g. 20260131)")
    merge_parser.add_argument("-w", "--workdir", help="Base workspace directory")
    merge_parser.add_argument("-o", "--output", help="Output file path")

    args = parser.parse_args()
    
    if args.command == "build":
        build_podcast(args.input, args.output, args.workdir, args.verbose, args.force)
    elif args.command == "check":
        check_script(args.input, args.workdir, args.verbose)
    elif args.command == "init":
        init_project(args.name)
    elif args.command == "config":
        manage_config(init=args.init)
    elif args.command == "rss":
        generate_rss(args.project_dir)
    elif args.command == "audition":
        audition_voices(count=args.count, text=args.text, workdir=args.workdir)
    elif args.command == "merge":
        merge_segments(args.episode, args.workdir, args.output)



if __name__ == "__main__":
    main()
