"""Text-to-speech output."""

import os
import platform
import subprocess
import tempfile

from config import Config


def speak(text: str, config: Config):
    """Speak text aloud using available TTS engine."""
    if not config.tts_enabled:
        return

    # Truncate very long responses for TTS
    if len(text) > 500:
        text = text[:500] + "... I've saved the full response."

    system = platform.system()

    # Try edge-tts first (cross-platform, best quality)
    if _try_edge_tts(text, config):
        return

    # Fallback: macOS native TTS
    if system == "Darwin":
        _macos_say(text)
        return

    # Fallback: Linux espeak
    if system == "Linux":
        _linux_espeak(text)
        return

    print(f"  🔇 No TTS engine available. Response: {text[:100]}")


def _try_edge_tts(text: str, config: Config) -> bool:
    """Try edge-tts (best quality, needs internet)."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name

        result = subprocess.run([
            "edge-tts",
            "--text", text,
            "--voice", config.tts_voice,
            "--rate", config.tts_rate,
            "--write-media", tmp_path
        ], capture_output=True, timeout=30)

        if result.returncode != 0:
            return False

        # Play the audio
        _play_audio(tmp_path)
        os.unlink(tmp_path)
        return True

    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    except Exception:
        return False


def _play_audio(path: str):
    """Play an audio file using available player."""
    system = platform.system()

    try:
        if system == "Darwin":
            subprocess.run(["afplay", path], timeout=60)
        elif system == "Linux":
            # Try multiple players
            for player in ["mpv --no-video", "ffplay -nodisp -autoexit", "aplay"]:
                parts = player.split()
                try:
                    subprocess.run([*parts, path], capture_output=True, timeout=60)
                    return
                except FileNotFoundError:
                    continue
    except subprocess.TimeoutExpired:
        pass


def _macos_say(text: str):
    """macOS native TTS."""
    try:
        subprocess.run(["say", text], timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _linux_espeak(text: str):
    """Linux espeak TTS (low quality fallback)."""
    try:
        subprocess.run(["espeak", text], capture_output=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
