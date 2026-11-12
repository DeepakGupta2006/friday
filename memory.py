"""Conversation memory + 'remember that...' notes, saved to memory.json."""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")
MAX_MESSAGES = 12


class Memory:
    def __init__(self):
        self.history: list = []
        self.notes: list = []
        try:
            with open(PATH, encoding="utf-8") as f:
                data = json.load(f)
            self.history = data.get("history", [])[-MAX_MESSAGES:]
            self.notes = data.get("notes", [])
        except (FileNotFoundError, ValueError):
            pass

    def _save(self):
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump({"history": self.history, "notes": self.notes}, f, indent=2)

    def add_turn(self, user: str, assistant: str):
        self.history += [
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
        self.history = self.history[-MAX_MESSAGES:]
        self._save()

    def add_note(self, note: str):
        self.notes.append(note)
        self._save()

    def clear(self):
        self.history, self.notes = [], []
        self._save()
