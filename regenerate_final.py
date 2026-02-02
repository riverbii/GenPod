
import os
import subprocess
from pathlib import Path

# Configuration
GENPOD_ROOT = Path("/Users/bixinfang/project/GenPod")
SEGMENTS_MD_DIR = Path("/Users/bixinfang/project/RiverPod-private/workspace/output/20260131/20260131_segments_md")
OUTPUT_WAV_DIR = Path("/Users/bixinfang/project/RiverPod-private/workspace/output/20260131/segments")
SEED = "7470000"
TARGET_INDICES = [2, 3, 5, 6, 7, 8, 9, 10, 11]

def run():
    os.chdir(GENPOD_ROOT)
    for idx in TARGET_INDICES:
        pattern = f"segment_{idx:03d}_*.md"
        matches = list(SEGMENTS_MD_DIR.glob(pattern))
        if not matches: continue
        md_file = matches[0]
        output_wav = OUTPUT_WAV_DIR / f"segment_{idx:03d}.wav"
        print(f"🔄 Regenerating Segment {idx:03d}...")
        cmd = [
            "uv", "run", "python", "-m", "src.genpod.generate_podcast",
            str(md_file), "-o", str(output_wav), "-v", SEED
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print("   ✅ Done")
        except Exception as e:
            print(f"   ❌ Failed: {e}")

if __name__ == "__main__":
    run()
