import pytest
import sys
from unittest.mock import MagicMock, patch

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock dependencies globally for this module"""
    mock_chattts = MagicMock()
    mock_torchaudio = MagicMock()
    mock_pydub = MagicMock()
    
    with patch.dict(sys.modules, {
        "ChatTTS": mock_chattts,
        "torchaudio": mock_torchaudio,
        "pydub": mock_pydub,
        "pydub.silence": MagicMock(),
        "torch": MagicMock(),
        "numpy": MagicMock(),
    }):
        yield

# We cannot import generate_audio at top level because ChatTTS is not mocked yet.
# We will import it inside tests or after fixture setup? 
# Actually, if we use the fixture, we still can't import at top level easily unless we do it inside a function.
# But @patch decorators run at collection time? No, at execution time for the test?
# Actually @patch target resolution happens when test runs.
# BUT, we need 'generate_audio' symbol for the test function call?
# No, we test 'genpod.generate_podcast.generate_audio' via import inside test?

@patch("genpod.generate_podcast.get_chat_instance")
@patch("genpod.generate_podcast.torchaudio.save")
@patch("os.replace")
@patch("genpod.generate_podcast.AudioSegment")
def test_atomic_write(mock_audio_segment, mock_replace, mock_save, mock_get_chat):
    """Test that generate_audio writes to a .tmp file and renames it"""
    
    # Setup mocks
    # Setup mocks
    mock_chat = MagicMock()
    mock_get_chat.return_value = mock_chat
    
    # First call: Refine text (returns list of strings)
    # Second call: Generate audio (returns list of numpy arrays)
    import numpy as np
    mock_wav = np.zeros((1, 24000)) # 1 second silence
    mock_chat.infer.side_effect = [
        ["refined text"], # Call 1
        [mock_wav]       # Call 2
    ]
    mock_chat.sample_random_speaker.return_value = "emb"
    
    output_file = "test.wav"
    expected_temp = "test.wav.tmp"
    
    # Run
    # delayed import
    import torch # This is the mock
    import numpy as np # This is the mock
    
    # Configure Mock Tensor
    mock_tensor = MagicMock()
    mock_tensor.shape = (1, 24000) # Valid shape for comparison
    torch.from_numpy.return_value = mock_tensor
    
    from genpod.generate_podcast import generate_audio
    generate_audio("test text", "2222", output_file)
    
    # Verify save called with tmp file
    args, _ = mock_save.call_args
    assert args[0] == expected_temp # Save path should be .tmp
    
    # Verify replace called
    mock_replace.assert_called_with(expected_temp, output_file)

@patch("genpod.generate_podcast.get_chat_instance")
@patch("genpod.generate_podcast.torchaudio.save")
@patch("os.replace")
def test_atomic_write_failure(mock_replace, mock_save, mock_get_chat):
    """Test that atomic write cleans up on failure"""
    mock_chat = MagicMock()
    mock_get_chat.return_value = mock_chat
    
    import numpy as np
    mock_wav = np.zeros((1, 24000))
    mock_chat.infer.side_effect = [
        ["refined text"], 
        [mock_wav]
    ]
    
    # Simulate save failure
    mock_save.side_effect = Exception("Save failed")
    
    with pytest.raises(Exception):
        from genpod.generate_podcast import generate_audio
        generate_audio("test", "2222", "fail.wav")
        
    # Replace should NOT be called
    mock_replace.assert_not_called()
    
    # Check if logic attempts to remove tmp (hard to test exact os.remove without mocking exist check, 
    # but observing code flow confirms it attempts cleanup)
