"""Route classified intents to appropriate actions."""

from datetime import datetime
from pathlib import Path

from config import Config
from claude_bridge import ClaudeBridge


class Router:
    """Route intents to actions."""

    def __init__(self, config: Config, claude: ClaudeBridge):
        self.config = config
        self.claude = claude
        self.vault = Path(config.vault_path)

    def route(self, intent: str, text: str) -> str | None:
        """
        Route an intent to the appropriate action.

        Returns a response string (for TTS) or None.
        """
        handlers = {
            "QUESTION": self._handle_question,
            "IDEA": self._handle_idea,
            "TASK": self._handle_task,
            "NOTE": self._handle_note,
            "IGNORE": self._handle_ignore,
        }

        handler = handlers.get(intent, self._handle_ignore)
        return handler(text)

    def _handle_question(self, text: str) -> str:
        """Send to Claude Code CLI and return response."""
        print(f"  🤖 Asking Claude: \"{text[:60]}...\"")
        response = self.claude.ask(text)
        print(f"  💬 Claude: {response[:100]}...")
        return response

    def _handle_idea(self, text: str) -> str:
        """Save idea to Obsidian Inbox."""
        inbox = self.vault / "Inbox"
        inbox.mkdir(parents=True, exist_ok=True)

        ideas_file = inbox / "ideas.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        entry = f"\n- [ ] **{timestamp}** — {text}\n"

        # Append to ideas file
        if ideas_file.exists():
            content = ideas_file.read_text()
        else:
            content = "# Ideas\n\nCaptured ideas from voice input.\n"

        content += entry
        ideas_file.write_text(content)

        print(f"  💡 Idea saved to {ideas_file}")
        return f"Got it, idea saved: {text[:50]}"

    def _handle_task(self, text: str) -> str:
        """Save task to Obsidian Tasks."""
        tasks_dir = self.vault / "Tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        tasks_file = tasks_dir / f"{today}.md"

        timestamp = datetime.now().strftime("%H:%M")
        entry = f"\n- [ ] {text} *(added {timestamp} via voice)*\n"

        if tasks_file.exists():
            content = tasks_file.read_text()
        else:
            content = f"# Tasks — {today}\n"

        content += entry
        tasks_file.write_text(content)

        print(f"  ✅ Task saved to {tasks_file}")
        return f"Task added: {text[:50]}"

    def _handle_note(self, text: str) -> str:
        """Save note to Obsidian Inbox."""
        inbox = self.vault / "Inbox"
        inbox.mkdir(parents=True, exist_ok=True)

        notes_file = inbox / "voice-notes.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        entry = f"\n### {timestamp}\n{text}\n"

        if notes_file.exists():
            content = notes_file.read_text()
        else:
            content = "# Voice Notes\n\nNotes captured from voice input.\n"

        content += entry
        notes_file.write_text(content)

        print(f"  📝 Note saved to {notes_file}")
        return f"Note saved."

    def _handle_ignore(self, text: str) -> None:
        """Ignored utterance — no action."""
        return None
