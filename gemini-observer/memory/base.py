from abc import ABC, abstractmethod
from typing import List, Dict, Any

class MemoryProvider(ABC):
    """
    Abstract Base Class for memory providers.
    """

    @abstractmethod
    async def add_message(self, role: str, content: str):
        """
        Adds a message to the history.
        :param role: 'user', 'model', or 'system'
        :param content: The text content of the message
        """
        pass

    @abstractmethod
    async def get_history(self) -> List[Dict[str, Any]]:
        """
        Retrieves the conversation history.
        :return: A list of message dictionaries.
        """
        pass
