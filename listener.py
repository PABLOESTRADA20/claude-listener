#!/usr/bin/env python3
"""
Claude Listener — Always-on voice assistant.

Listens for a wake word, transcribes speech with Whisper,
classifies intent with a local LLM (ollama), and routes to:
  - Claude Code CLI for questions
  - Obsidian vault for ideas/tasks
  - TTS for voice responses

Works on macOS and Linux.
"""

import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

# Audio recording
try:
    import sounddevice as sd
    import numpy as np
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

from config import Config
from router import Router
from transcriber import Transcriber
from classifier import Classifier
from claude_bridge import ClaudeBridge
from tts import speak

def check_dependencies():
    """Check and report missing dependencies."""
    missing = []
    if not HAS_AUDIO:
        missing.append("sounddevice numpy (pip install sounddevice numpy)")

    # Check whisper
    try:
        subprocess.run(["whisper", "--help"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        try:
            import whisper
        except ImportError:
            missing.append("whisper (pip install openai-whisper)")

    # Check ollama
    try:
        subprocess.run(["ollama", "--version"], capture_output=True, timeout=5)
    except FileNotFoundError:
        missing.append("ollama (https://ollama.ai)")

# Check claude
    try:
        subprocess.run(["claude", "--version"], capture_output=True, timeout=5)
    except FileNotFoundError:
        try:
            subprocess.run(["claude.cmd", "--version"], capture_output=True, timeout=5)
        except FileNotFoundError:
            missing.append("claude CLI (npm install -g @anthropic-ai/claude-code)")

    return missing


class VoiceActivityDetector:
    """Simple energy-based VAD."""

    def __init__(self, threshold: float = 0.02, silence_duration: float = 1.5):
        self.threshold = threshold
        self.silence_duration = silence_duration

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """Check if audio chunk contains speech based on RMS energy."""
        rms = np.sqrt(np.mean(audio_chunk.astype(float) ** 2))
        return rms > self.threshold


class Listener:
    """Main always-on listening loop."""

    def __init__(self, config: Config):
        self.config = config
        self.vad = VoiceActivityDetector(
            threshold=config.vad_threshold,
            silence_duration=config.silence_duration
        )
        self.transcriber = Transcriber(config)
        self.classifier = Classifier(config)
        self.claude = ClaudeBridge(config)
        self.router = Router(config, self.claude)
        self.audio_queue = queue.Queue()
        self.running = False

    def start(self):
        """Start the listening loop."""
        if not HAS_AUDIO:
            print("Error: sounddevice not installed. Run: pip install sounddevice numpy")
            sys.exit(1)

        self.running = True
        print(f"""
╔══════════════════════════════════════════╗
║   Claude Listener — Always On           ║
╚══════════════════════════════════════════╝

  Wake word:     "{self.config.wake_word}"
  Mode:          {self.config.mode}
  Whisper model: {self.config.whisper_model}
  Local LLM:     {self.config.ollama_model}
  Vault:         {self.config.vault_path}

  Listening... (Ctrl+C to stop)
""")

        if self.config.mode == "wake_word":
            self._run_wake_word_mode()
        elif self.config.mode == "continuous":
            self._run_continuous_mode()
        elif self.config.mode == "push_to_talk":
            self._run_push_to_talk_mode()

    def _run_wake_word_mode(self):
        """Listen for wake word, then record and process."""
        print(f"  Say \"{self.config.wake_word}\" to activate...\n")

        # Continuous short recordings to detect wake word
        while self.running:
            try:
                # Record a short chunk for wake word detection
                audio = self._record_chunk(duration=3.0)
                if audio is None:
                    continue

                text = self.transcriber.transcribe(audio, quick=True)
                if not text:
                    continue

                # Check for wake word
                if self.config.wake_word.lower() in text.lower():
                    print("  🎤 Wake word detected! Listening...")

                    # Check if there's already a command after the wake word
                    after_wake = text.lower().split(self.config.wake_word.lower(), 1)[-1].strip()

                    if len(after_wake) > 5:
                        # Command was in the same utterance
                        self._process_utterance(after_wake)
                    else:
                        # Play a beep/indicator
                        if self.config.sound_feedback:
                            speak("Yes?", self.config)

                        # Record the actual command
                        audio = self._record_until_silence()
                        if audio is not None:
                            text = self.transcriber.transcribe(audio)
                            if text:
                                self._process_utterance(text)

                    print(f"\n  Say \"{self.config.wake_word}\" to activate...\n")

            except KeyboardInterrupt:
                self.running = False
                print("\n  Stopped.")
                break

    def _run_continuous_mode(self):
        """Continuously transcribe and classify everything."""
        print("  Continuous mode — classifying all speech...\n")

        while self.running:
            try:
                audio = self._record_until_silence()
                if audio is None:
                    continue

                text = self.transcriber.transcribe(audio)
                if not text or len(text.strip()) < 3:
                    continue

                print(f"  📝 Heard: \"{text[:80]}...\"" if len(text) > 80 else f"  📝 Heard: \"{text}\"")

                # Classify with local LLM
                intent = self.classifier.classify(text)
                print(f"  🏷️  Intent: {intent}")

                if intent != "IGNORE":
                    self._process_utterance(text, intent=intent)

            except KeyboardInterrupt:
                self.running = False
                print("\n  Stopped.")
                break

    def _run_push_to_talk_mode(self):
        """Wait for Enter key, record, process."""
        print("  Push-to-talk mode — press Enter to start recording, Enter again to stop.\n")

        while self.running:
            try:
                input("  Press Enter to record...")
                print("  🎤 Recording... (press Enter to stop)")

                # Record in background until Enter
                recording = []
                stop_event = threading.Event()

                def record_thread():
                    while not stop_event.is_set():
                        chunk = sd.rec(
                            int(0.5 * self.config.sample_rate),
                            samplerate=self.config.sample_rate,
                            channels=1, dtype='int16'
                        )
                        sd.wait()
                        recording.append(chunk)

                t = threading.Thread(target=record_thread, daemon=True)
                t.start()
                input()  # Wait for Enter
                stop_event.set()
                t.join(timeout=1)

                if recording:
                    audio = np.concatenate(recording)
                    text = self.transcriber.transcribe(audio)
                    if text:
                        self._process_utterance(text)

            except KeyboardInterrupt:
                self.running = False
                print("\n  Stopped.")
                break

    def _record_chunk(self, duration: float = 3.0) -> np.ndarray | None:
        """Record a fixed-duration audio chunk."""
        try:
            audio = sd.rec(
                int(duration * self.config.sample_rate),
                samplerate=self.config.sample_rate,
                channels=1, dtype='int16'
            )
            sd.wait()
            return audio.flatten()
        except Exception as e:
            print(f"  ⚠️  Recording error: {e}")
            return None

    def _record_until_silence(self, max_duration: float = 30.0) -> np.ndarray | None:
        """Record audio until silence is detected."""
        chunk_size = int(0.3 * self.config.sample_rate)  # 300ms chunks
        max_chunks = int(max_duration / 0.3)
        silence_chunks_needed = int(self.config.silence_duration / 0.3)

        chunks = []
        silence_count = 0
        speech_detected = False

        try:
            for _ in range(max_chunks):
                chunk = sd.rec(chunk_size, samplerate=self.config.sample_rate,
                             channels=1, dtype='int16')
                sd.wait()
                chunk = chunk.flatten()
                chunks.append(chunk)

                if self.vad.is_speech(chunk):
                    speech_detected = True
                    silence_count = 0
                else:
                    silence_count += 1

                if speech_detected and silence_count >= silence_chunks_needed:
                    break

            if not speech_detected:
                return None

            return np.concatenate(chunks)

        except Exception as e:
            print(f"  ⚠️  Recording error: {e}")
            return None

    def _process_utterance(self, text: str, intent: str = None):
        """Process a transcribed utterance."""
        if intent is None:
            intent = self.classifier.classify(text)
            print(f"  🏷️  Intent: {intent}")

        result = self.router.route(intent, text)

        if result and self.config.tts_enabled:
            speak(result, self.config)


def main():
    parser = argparse.ArgumentParser(description="Claude Listener — Always-on voice assistant")
    parser.add_argument("--mode", choices=["wake_word", "continuous", "push_to_talk"],
                       default=None, help="Listening mode")
    parser.add_argument("--wake-word", default=None, help="Wake word phrase")
    parser.add_argument("--whisper-model", default=None, help="Whisper model size")
    parser.add_argument("--ollama-model", default=None, help="Ollama model for classification")
    parser.add_argument("--vault", default=None, help="Obsidian vault path")
    parser.add_argument("--no-tts", action="store_true", help="Disable TTS responses")
    parser.add_argument("--list-devices", action="store_true", help="List audio input devices")
    parser.add_argument("--device", type=int, default=None, help="Audio input device index")
    parser.add_argument("--check", action="store_true", help="Check dependencies and exit")

    args = parser.parse_args()

    if args.list_devices:
        if not HAS_AUDIO:
            print("Install sounddevice first: pip install sounddevice")
            sys.exit(1)
        print(sd.query_devices())
        sys.exit(0)

    if args.check:
        missing = check_dependencies()
        if missing:
            print("Missing dependencies:")
            for m in missing:
                print(f"  - {m}")
            sys.exit(1)
        else:
            print("All dependencies OK!")
            sys.exit(0)

    # Load config
    config = Config.load()

    # CLI overrides
    if args.mode:
        config.mode = args.mode
    if args.wake_word:
        config.wake_word = args.wake_word
    if args.whisper_model:
        config.whisper_model = args.whisper_model
    if args.ollama_model:
        config.ollama_model = args.ollama_model
    if args.vault:
        config.vault_path = args.vault
    if args.no_tts:
        config.tts_enabled = False
    if args.device is not None:
        sd.default.device = args.device

    # Check deps
    missing = check_dependencies()
    if missing:
        print("Missing dependencies:")
        for m in missing:
            print(f"  - {m}")
        print("\nInstall them and try again.")
        sys.exit(1)

    listener = Listener(config)
    listener.start()


if __name__ == "__main__":
    main()
