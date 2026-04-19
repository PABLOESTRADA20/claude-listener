# Claude Listener

Always-on voice assistant that listens, classifies intent with a local LLM, and routes to Claude Code when needed. Ideas and tasks go straight to your Obsidian vault.

## How It Works

```
🎤 Microphone (always on)
    ↓
🗣️ Whisper (local STT)
    ↓
🧠 Ollama / local LLM (classify intent)
    ↓
┌─────────────────────────────────────┐
│ QUESTION → Claude Code CLI          │
│ IDEA     → Obsidian Inbox/ideas.md  │
│ TASK     → Obsidian Tasks/today.md  │
│ NOTE     → Obsidian Inbox/notes.md  │
│ IGNORE   → (nothing)               │
└─────────────────────────────────────┘
    ↓
🔊 edge-tts (voice response)
```

## Quick Start

```bash
git clone https://github.com/4rdii/claude-listener.git
cd claude-listener

# Install everything (macOS or Linux)
chmod +x setup.sh
./setup.sh

# Make sure ollama is running
ollama serve &

# Start listening
python3 listener.py
```

## Modes

| Mode | How it works | Best for |
|------|-------------|----------|
| `wake_word` (default) | Say "hey claude" to activate | Hands-free, low battery |
| `continuous` | Classifies ALL speech | Capturing ideas on the fly |
| `push_to_talk` | Press Enter to record | Noisy environments |

```bash
python3 listener.py --mode wake_word       # default
python3 listener.py --mode continuous
python3 listener.py --mode push_to_talk
```

## Options

```bash
python3 listener.py \
  --wake-word "ok assistant" \   # custom wake phrase
  --whisper-model base \         # tiny|base|small|medium (accuracy vs speed)
  --ollama-model llama3.2:3b \   # any ollama model
  --vault ~/obsidian-vault \     # your vault path
  --no-tts \                     # disable voice responses
  --device 2                     # select microphone
```

## Requirements

- **Python 3.10+**
- **Ollama** — local LLM for intent classification ([ollama.ai](https://ollama.ai))
- **Claude CLI** — `npm install -g @anthropic-ai/claude-code` (needs Claude Pro/Max)
- **PortAudio** — for microphone access (`brew install portaudio` / `apt install portaudio19-dev`)
- **ffmpeg** — for audio playback (`brew install ffmpeg` / `apt install ffmpeg`)

## Architecture

### Layer 1: Continuous Listening
- `sounddevice` captures microphone input
- Simple energy-based VAD (Voice Activity Detection) filters silence
- Records until speech stops (configurable silence duration)

### Layer 2: Transcription
- OpenAI Whisper (runs locally, no API needed)
- `tiny` model for wake word detection (fast), larger models for actual transcription

### Layer 3: Intent Classification
- Local LLM via Ollama (default: `qwen2.5:3b`)
- Zero API cost, ~200ms inference
- Classifies into: QUESTION, IDEA, TASK, NOTE, IGNORE
- Falls back to keyword heuristics if Ollama is unavailable

### Layer 4: Action Routing
- **QUESTION** → `claude --print --resume SESSION_ID "prompt"` → TTS response
- **IDEA** → appends to `Inbox/ideas.md` with timestamp
- **TASK** → appends to `Tasks/YYYY-MM-DD.md`
- **NOTE** → appends to `Inbox/voice-notes.md`

### Layer 5: Response
- `edge-tts` for high-quality voice (needs internet)
- Falls back to macOS `say` or Linux `espeak`

## Config

Config lives at `~/.claude-listener/config.json`:

```json
{
  "mode": "wake_word",
  "wake_word": "hey claude",
  "whisper_model": "tiny",
  "ollama_model": "qwen2.5:3b",
  "vault_path": "~/obsidian-vault",
  "tts_enabled": true,
  "tts_voice": "en-US-GuyNeural",
  "vad_threshold": 0.02,
  "silence_duration": 1.5
}
```

## Privacy

- All speech processing happens **locally** (Whisper + Ollama)
- Only QUESTION intents are sent to Claude (via CLI, using your subscription)
- No audio is stored permanently — only text transcripts if `log_transcripts` is enabled
- You control what gets saved to your vault

## License

MIT
