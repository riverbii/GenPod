from pathlib import Path
from unittest.mock import patch
import sys

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from genpod.cli import merge_segments

def test_merge_segments_missing_gap(tmp_path):
    """Test that merge_segments fails if segments have gap"""
    # Setup: Create segments 001, 002, 004 (Missing 003)
    # workdir/output/test_episode/test_episode_segments_md
    episode_name = "test_episode"
    segments_dir = tmp_path / "output" / episode_name / f"{episode_name}_segments_md"
    segments_dir.mkdir(parents=True)
    
    (segments_dir / "segment_001_deadbeef.md").write_text("S1")
    (segments_dir / "segment_002_deadbeef.md").write_text("S2")
    # Missing 003
    (segments_dir / "segment_004_deadbeef.md").write_text("S4")
    
    # Run merge, expect exit(1)
    with patch("sys.exit") as mock_exit:
        merge_segments("test_episode", workdir=str(tmp_path))
        mock_exit.assert_called_with(1)

def test_merge_segments_success(tmp_path):
    """Test that merge_segments succeeds with continuous segments"""
    # Setup: Create segments 001, 002, 003
    episode_name = "test_success"
    segments_dir = tmp_path / "output" / episode_name / f"{episode_name}_segments_md"
    segments_dir.mkdir(parents=True)
    
    (segments_dir / "segment_001_deadbeef.md").write_text("S1")
    (segments_dir / "segment_002_deadbeef.md").write_text("S2")
    (segments_dir / "segment_003_deadbeef.md").write_text("S3")
    
    output_file = tmp_path / "out.md"
    
    # Run merge
    with patch("sys.exit") as mock_exit:
        merge_segments("test_success", workdir=str(tmp_path), output_file=str(output_file))
        # Should not exit
        mock_exit.assert_not_called()
    
    assert output_file.exists()
    content = output_file.read_text("utf-8")
    assert "S1" in content
    assert "S2" in content
    assert "S3" in content
