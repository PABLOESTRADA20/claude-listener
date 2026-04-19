"""Intent classification using local LLM (ollama)."""

import json
import subprocess
from urllib.request import Request, urlopen
from urllib.error import URLError

from config import Config


SYSTEM_PROMPT = """You are a voice command classifier. Given a transcribed utterance, classify it into exactly ONE of these categories:

QUESTION — User is asking a question or wants Claude to do something (code, research, explain, create, search, etc.)
IDEA — User is expressing an idea, insight, or thought they want to capture/save
TASK — User is describing something they need to do, a reminder, or a to-do item
NOTE — User wants to save a note or piece of information
IGNORE — Background conversation, filler words, unclear speech, or not directed at the assistant

Respond with ONLY the category name, nothing else. No explanation.

Examples:
"how does quicksort work" → QUESTION
"I should build a tool that tracks gas prices" → IDEA
"remind me to call the dentist tomorrow" → TASK
"the API endpoint is api.example.com slash v2" → NOTE
"um yeah so anyway" → IGNORE
"what's the weather" → QUESTION
"we could use websockets instead of polling for the dashboard" → IDEA
"I need to review the PR before Monday" → TASK
"""


class Classifier:
    """Classify utterances using a local LLM via ollama."""

    def __init__(self, config: Config):
        self.config = config
        self._check_ollama()

    def _check_ollama(self):
        """Verify ollama is running and model is available."""
        try:
            req = Request(f"{self.config.ollama_url}/api/tags")
            with urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
                model_base = self.config.ollama_model.split(":")[0]
                if not any(model_base in m for m in models):
                    print(f"  ⚠️  Model '{self.config.ollama_model}' not found in ollama.")
                    print(f"     Run: ollama pull {self.config.ollama_model}")
                    print(f"     Available: {', '.join(models[:5])}")
        except (URLError, Exception) as e:
            print(f"  ⚠️  Cannot reach ollama at {self.config.ollama_url}")
            print(f"     Make sure ollama is running: ollama serve")

    def classify(self, text: str) -> str:
        """
        Classify text into an intent category.

        Returns: QUESTION, IDEA, TASK, NOTE, or IGNORE
        """
        try:
            payload = json.dumps({
                "model": self.config.ollama_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_predict": 10,  # We only need one word
                }
            }).encode()

            req = Request(
                f"{self.config.ollama_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                response = result.get("message", {}).get("content", "").strip().upper()

                # Extract the category from response
                for category in ["QUESTION", "IDEA", "TASK", "NOTE", "IGNORE"]:
                    if category in response:
                        return category

                return "IGNORE"

        except Exception as e:
            print(f"  ⚠️  Classification failed: {e}")
            # Fallback: simple keyword heuristics
            return self._fallback_classify(text)

    def _fallback_classify(self, text: str) -> str:
        """Simple keyword-based fallback when ollama is unavailable."""
        text_lower = text.lower()

        # Question indicators
        question_words = ["what", "how", "why", "when", "where", "who",
                         "can you", "could you", "explain", "tell me",
                         "search", "find", "look up", "create", "build",
                         "write", "code", "debug", "fix"]
        if any(text_lower.startswith(w) or f" {w} " in f" {text_lower} " for w in question_words):
            return "QUESTION"
        if text_lower.endswith("?"):
            return "QUESTION"

        # Task indicators
        task_words = ["remind", "todo", "need to", "have to", "must",
                     "don't forget", "schedule", "deadline", "before"]
        if any(w in text_lower for w in task_words):
            return "TASK"

        # Idea indicators
        idea_words = ["idea", "what if", "we could", "we should",
                     "imagine", "concept", "thought", "maybe we"]
        if any(w in text_lower for w in idea_words):
            return "IDEA"

        # Note indicators
        note_words = ["note", "remember that", "save this", "the address is",
                     "the password is", "the url is", "write down"]
        if any(w in text_lower for w in note_words):
            return "NOTE"

        return "IGNORE"
