from typing import List, Dict, Any
from .base import MemoryProvider

class InMemoryProvider(MemoryProvider):
    """
    Simple in-memory storage for conversation history.
    Not persistent across restarts.
    """
    def __init__(self):
        self._history: List[Dict[str, Any]] = []

    async def add_message(self, role: str, content: str):
        self._history.append({"role": role, "parts": [content]})

    async def get_history(self) -> List[Dict[str, Any]]:
        return self._history
