"""Speech-to-text using Whisper."""

import subprocess
import tempfile
import os
import numpy as np
from pathlib import Path

from config import Config


class Transcriber:
    """Transcribe audio using Whisper CLI or Python API."""

    def __init__(self, config: Config):
        self.config = config
        self._use_python_api = False

        # Try CLI first, fall back to Python API
        try:
            subprocess.run(["whisper", "--help"], capture_output=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            try:
                import whisper
                self._model = whisper.load_model(config.whisper_model)
                self._use_python_api = True
            except ImportError:
                raise RuntimeError("Whisper not found. Install: pip install openai-whisper")

    def transcribe(self, audio: np.ndarray, quick: bool = False) -> str:
        """
        Transcribe audio array to text.

        Args:
            audio: numpy int16 audio array at config.sample_rate
            quick: if True, use fastest possible model for wake word detection
        """
        if self._use_python_api:
            return self._transcribe_python(audio)
        else:
            return self._transcribe_cli(audio, quick)

    def _transcribe_cli(self, audio: np.ndarray, quick: bool = False) -> str:
        """Transcribe using whisper CLI."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
            self._write_wav(f, audio)

        try:
            model = "tiny" if quick else self.config.whisper_model
            cmd = [
                "whisper", tmp_path,
                "--model", model,
                "--language", self.config.whisper_language,
                "--output_format", "txt",
                "--output_dir", tempfile.gettempdir(),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            # Read the output text file
            txt_path = Path(tmp_path).with_suffix(".txt")
            if txt_path.exists():
                text = txt_path.read_text().strip()
                txt_path.unlink(missing_ok=True)
                return text

            return ""
        except subprocess.TimeoutExpired:
            return ""
        finally:
            os.unlink(tmp_path)

    def _transcribe_python(self, audio: np.ndarray) -> str:
        """Transcribe using whisper Python API."""
        import whisper

        # Convert int16 to float32
        audio_float = audio.astype(np.float32) / 32768.0

        result = self._model.transcribe(
            audio_float,
            language=self.config.whisper_language,
            fp16=False,
        )
        return result.get("text", "").strip()

    def _write_wav(self, f, audio: np.ndarray):
        """Write a simple WAV file."""
        import struct

        num_samples = len(audio)
        data_size = num_samples * 2  # 16-bit = 2 bytes per sample

        # WAV header
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + data_size))
        f.write(b'WAVE')
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))  # chunk size
        f.write(struct.pack('<H', 1))   # PCM format
        f.write(struct.pack('<H', 1))   # mono
        f.write(struct.pack('<I', self.config.sample_rate))
        f.write(struct.pack('<I', self.config.sample_rate * 2))  # byte rate
        f.write(struct.pack('<H', 2))   # block align
        f.write(struct.pack('<H', 16))  # bits per sample
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        f.write(audio.tobytes())
