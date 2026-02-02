import asyncio
import logging
from memory.base import MemoryProvider
from core.llm_interface import LLMProvider
from core.providers.gemini_provider import GeminiProvider
from core.providers.ollama_provider import OllamaProvider
from transport.queue import RedisQueue

class RalphLoop:
    """
    The main decision loop of the agent (OODA Loop).
    Observe -> Orient -> Decide -> Act
    Async Worker Mode.
    Now equipped with Local Cortex (Circuit Breaker).
    """
    def __init__(self, memory: MemoryProvider, client: GeminiProvider, queue: RedisQueue):
        # Note: 'client' argument kept for backward compatibility in main.py, 
        # but we will instantiate our own providers or wrap them.
        self.memory = memory
        self.queue = queue
        self.running = False
        
        # Initialize Providers
        self.main_provider: LLMProvider = client if isinstance(client, GeminiProvider) else GeminiProvider()
        
        # For the backup provider, we might want to config the host.
        # Assuming 'ollama' is the hostname in the docker network.
        # If running mostly locally outside docker, this might need 'localhost'.
        self.backup_provider: LLMProvider = OllamaProvider(host="http://falkordb-ollama:11434", model="gemma2:2b")

    async def run_worker(self):
        """
        Infinite loop to process events from the incoming queue.
        """
        self.running = True
        logging.info("Starting RalphLoop Worker with Local Cortex protection...")
        
        while self.running:
            try:
                # Step 0: Dequeue
                event = await self.queue.pop_incoming()
                if not event:
                    await asyncio.sleep(0.1)
                    continue
                
                logging.info(f"Processing event: {event.get('message_id')}")
                
                user_id = event.get("user_id")
                chat_id = event.get("chat_id")
                text = event.get("text")
                
                if not text:
                    continue

                # Step 1: Observe (Store input)
                await self.memory.add_message("user", text)

                # Step 2: Orient (Retrieve context)
                history = await self.memory.get_history()

                # Step 3: Decide & Act (Generate response)
                response_text = ""
                try:
                    # Attempt 1: Main Provider (Gemini)
                    response_text = await self.main_provider.generate_response(history)
                except Exception as e:
                    logging.error(f"⚠️ Gemini Fail: {e}. Switching to Local Cortex.")
                    
                    # Circuit Breaker Logic
                    # We could check for specific errors (429, 500), but for now fallback on ANY error
                    # is a safer "keep alive" strategy for the Ignition phase.
                    
                    try:
                        # Attempt 2: Backup Provider (Ollama)
                        # We might want to append a system instruction to history to keep it short?
                        # For now, just pass history.
                        response_text = await self.backup_provider.generate_response(history)
                    except Exception as e_local:
                        error_msg = f"System Critical Failure: All cognitive cores offline. ({e_local})"
                        logging.error(error_msg)
                        response_text = error_msg

                # Step 4: Store (Save response)
                # Note: We save whatever we generated, even if it's an error message
                await self.memory.add_message("model", response_text)

                # Step 5: Respond (Enqueue outgoing)
                outgoing_event = {
                    "chat_id": chat_id,
                    "text": response_text,
                    "original_message_id": event.get("message_id")
                }
                await self.queue.push_outgoing(outgoing_event)
                
            except Exception as e:
                logging.error(f"Error in RalphLoop: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        self.running = False
