"""Bridge to Claude Code CLI."""

import json
import subprocess
import os
from pathlib import Path

from config import Config


class ClaudeBridge:
    """Interact with Claude Code via the CLI."""

    def __init__(self, config: Config):
        self.config = config
        self.session_dir = Path(config.claude_session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.session_dir / "listener_session.json"
        self._session_id = self._load_session()

    def _load_session(self) -> str | None:
        """Load existing session ID for conversation continuity."""
        if self.session_file.exists():
            try:
                data = json.loads(self.session_file.read_text())
                return data.get("session_id")
            except (json.JSONDecodeError, Exception):
                pass
        return None

    def _save_session(self, session_id: str):
        """Save session ID for conversation continuity."""
        self.session_file.write_text(json.dumps({
            "session_id": session_id
        }))
        self._session_id = session_id

    def ask(self, prompt: str, new_session: bool = False) -> str:
        """
        Send a prompt to Claude Code CLI and return the response.

        Args:
            prompt: The question or command
            new_session: Force a new conversation session

        Returns: Claude's text response
        """
        cmd = [
            "claude",
            "--print",
            "--output-format", "json",
        ]

        # Add session continuity
        if self._session_id and not new_session:
            cmd.extend(["--resume", self._session_id])

        # Add project directory for context
        if self.config.claude_project_dir:
            cmd.extend(["--project-dir", self.config.claude_project_dir])

        # Add the prompt
        cmd.append(prompt)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
                env={**os.environ, "CLAUDE_CODE_ENTRYPOINT": "listener"}
            )

            if result.returncode != 0:
                error = result.stderr.strip()
                if "session" in error.lower():
                    # Session expired, try without resume
                    return self.ask(prompt, new_session=True)
                return f"Claude error: {error[:200]}"

            # Parse JSON output
            response_text = ""
            session_id = None

            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get("type") == "result":
                        response_text = msg.get("result", "")
                        session_id = msg.get("session_id")
                    elif msg.get("type") == "assistant":
                        # Accumulate content from assistant messages
                        content = msg.get("message", {}).get("content", [])
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                response_text += block.get("text", "")
                except json.JSONDecodeError:
                    # Plain text output
                    response_text += line

            # Save session for continuity
            if session_id:
                self._save_session(session_id)

            return response_text.strip() or "No response from Claude."

        except subprocess.TimeoutExpired:
            return "Claude took too long to respond."
        except FileNotFoundError:
            return "Claude CLI not found. Install: npm install -g @anthropic-ai/claude-code"
        except Exception as e:
            return f"Error calling Claude: {str(e)}"

    def new_session(self):
        """Start a fresh conversation."""
        self._session_id = None
        if self.session_file.exists():
            self.session_file.unlink()
