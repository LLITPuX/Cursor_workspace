from memory.base import MemoryProvider
from .gemini_client import GeminiClient

class RalphLoop:
    """
    The main decision loop of the agent (OODA Loop).
    Observe -> Orient -> Decide -> Act
    """
    def __init__(self, memory: MemoryProvider, client: GeminiClient):
        self.memory = memory
        self.client = client

    async def process_event(self, user_input: str) -> str:
        """
        Processes a user event (message) through the loop.
        """
        # Step 1: Observe (Store input)
        await self.memory.add_message("user", user_input)

        # Step 2: Orient (Retrieve context)
        history = await self.memory.get_history()

        # Step 3: Decide & Act (Generate response)
        try:
            response_text = await self.client.generate_response(history)
        except Exception as e:
            # Fallback for errors
            response_text = f"Error processing request: {str(e)}"

        # Step 4: Store (Save response)
        await self.memory.add_message("model", response_text)

        return response_text
