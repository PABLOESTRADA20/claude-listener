#!/usr/bin/env bash
set -euo pipefail

# Claude Listener — Setup script
# Works on macOS and Linux

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${CYAN}[info]${NC} $*"; }
ok()    { echo -e "${GREEN}[ok]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
err()   { echo -e "${RED}[error]${NC} $*"; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Claude Listener — Setup                ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

OS="$(uname -s)"

# ── System dependencies ─────────────────────────────────────────────────────

info "Checking system dependencies..."

# PortAudio (required by sounddevice)
if [[ "$OS" == "Darwin" ]]; then
    if ! brew list portaudio &>/dev/null 2>&1; then
        info "Installing PortAudio via Homebrew..."
        brew install portaudio
    fi
    ok "PortAudio (macOS/Homebrew)"

    # ffmpeg for audio playback
    if ! command -v ffplay &>/dev/null && ! command -v mpv &>/dev/null; then
        info "Installing ffmpeg for audio playback..."
        brew install ffmpeg
    fi
elif [[ "$OS" == "Linux" ]]; then
    if command -v apt-get &>/dev/null; then
        if ! dpkg -l libportaudio2 &>/dev/null 2>&1; then
            info "Installing PortAudio via apt..."
            sudo apt-get update && sudo apt-get install -y portaudio19-dev python3-pyaudio
        fi
        # ffmpeg for audio
        if ! command -v ffplay &>/dev/null; then
            sudo apt-get install -y ffmpeg
        fi
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm portaudio ffmpeg
    fi
    ok "PortAudio (Linux)"
fi

# ── Python dependencies ─────────────────────────────────────────────────────

info "Installing Python dependencies..."
pip3 install -r requirements.txt
ok "Python packages"

# ── Ollama ───────────────────────────────────────────────────────────────────

if ! command -v ollama &>/dev/null; then
    warn "Ollama not installed."
    echo ""
    echo "  Install it from https://ollama.ai"
    if [[ "$OS" == "Darwin" ]]; then
        echo "  Or: brew install ollama"
    elif [[ "$OS" == "Linux" ]]; then
        echo "  Or: curl -fsSL https://ollama.ai/install.sh | sh"
    fi
    echo ""
else
    ok "Ollama installed"

    # Pull default model
    MODEL="qwen2.5:3b"
    info "Pulling classifier model: $MODEL"
    ollama pull "$MODEL" 2>/dev/null || warn "Could not pull model. Run: ollama pull $MODEL"
    ok "Model ready: $MODEL"
fi

# ── Claude CLI ───────────────────────────────────────────────────────────────

if ! command -v claude &>/dev/null; then
    warn "Claude CLI not installed."
    echo "  Install: npm install -g @anthropic-ai/claude-code"
    echo "  Then authenticate: claude"
else
    ok "Claude CLI installed"
fi

# ── edge-tts ─────────────────────────────────────────────────────────────────

if ! command -v edge-tts &>/dev/null; then
    info "Installing edge-tts..."
    pip3 install edge-tts
fi
ok "edge-tts (TTS engine)"

# ── Create config ────────────────────────────────────────────────────────────

CONFIG_DIR="$HOME/.claude-listener"
mkdir -p "$CONFIG_DIR/sessions"

if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
    info "Creating default config at $CONFIG_DIR/config.json"
    python3 -c "from config import Config; Config().save()"
    ok "Config created"
else
    ok "Config exists"
fi

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "  Quick start:"
echo "    python3 listener.py                    # wake word mode (default)"
echo "    python3 listener.py --mode continuous   # classify all speech"
echo "    python3 listener.py --mode push_to_talk # press Enter to record"
echo ""
echo "  Options:"
echo "    --wake-word \"ok assistant\"    # custom wake word"
echo "    --whisper-model base          # larger model = better accuracy"
echo "    --ollama-model llama3.2:3b    # different classifier"
echo "    --vault ~/my-vault            # Obsidian vault path"
echo "    --no-tts                      # disable voice responses"
echo "    --list-devices                # show audio input devices"
echo "    --device 2                    # select mic by index"
echo "    --check                       # verify all dependencies"
echo ""
echo "  Config: $CONFIG_DIR/config.json"
echo ""
echo "  Make sure ollama is running: ollama serve"
echo ""
