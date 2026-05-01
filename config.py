"""Configuration management for Claude Listener."""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path


CONFIG_DIR = Path.home() / ".claude-listener"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    # Listening mode: wake_word, continuous, push_to_talk
    mode: str = "wake_word"

    # Wake word (used in wake_word mode)
    wake_word: str = "hey claude"

    # Audio settings
    sample_rate: int = 16000
    vad_threshold: float = 0.02
    silence_duration: float = 1.5  # seconds of silence to stop recording

    # Whisper settings
    whisper_model: str = "small"# tiny, base, small, medium
    whisper_language: str = "es"

    # Ollama settings (local LLM for classification)
    ollama_model: str = "qwen2.5:3b"  # small, fast, good at classification
    ollama_url: str = "http://localhost:11434"

    # Claude CLI settings
    claude_session_dir: str = str(Path.home() / ".claude-listener" / "sessions")
    claude_project_dir: str = ""  # optional: --project-dir for context

    # Obsidian vault
    vault_path: str = str(Path.home() / "obsidian-vault")

    # TTS settings
    tts_enabled: bool = True
    tts_voice: str = "es-MX-JorgeNeural"
    tts_rate: str = "+15%"

    # Feedback
    sound_feedback: bool = True

    # Logging
    log_file: str = str(CONFIG_DIR / "listener.log")
    log_transcripts: bool = True

    @classmethod
    def load(cls) -> "Config":
        """Load config from file, or create default."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    data = json.load(f)
                config = cls()
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                return config
            except (json.JSONDecodeError, Exception):
                pass

        config = cls()
        config.save()
        return config

    def save(self):
        """Save config to file."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(asdict(self), f, indent=2)
