import asyncio
import logging
from memory.base import MemoryProvider
from core.llm_interface import LLMProvider
from core.providers.gemini_provider import GeminiProvider
from core.providers.ollama_provider import OllamaProvider
from core.prompts import build_system_prompt, history_to_messages
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
        # FORCE LOCAL CORTEX Mode
        # We disable Gemini for now as per "Gemini CLI frozen" directive.
        
        # Configure Local Cortex (Gemma 3 4B)
        # Benchmark Winner: gemma3:4b (12 tok/s vs 7 tok/s for Mistral)
        local_provider = OllamaProvider(host="http://falkordb-ollama:11434", model="gemma3:4b")
        
        # Set Gemma 3 as MAIN and BACKUP provider
        self.main_provider: LLMProvider = local_provider
        self.backup_provider: LLMProvider = local_provider

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

                # ════════════════════════════════════════════════════════════════
                # BUILD CONTEXT: System Prompt + Chat History as Messages
                # ════════════════════════════════════════════════════════════════
                
                # Get system prompt (short, no history in it)
                system_prompt = build_system_prompt()
                
                # Fetch recent chat history from graph and convert to message format
                chat_messages = await self.memory.get_chat_context(chat_id, limit=10)
                history = history_to_messages(chat_messages)
                
                logging.info(f"Context: {len(history)} messages from history")
                
                # Step 3: Decide & Act (Generate response)
                response_text = ""
                try:
                    response_text = await self.main_provider.generate_response(
                        history=history,
                        system_prompt=system_prompt
                    )
                except Exception as e:
                    logging.error(f"⚠️ Main Provider Fail: {e}. Switching to backup...")
                    
                    try:
                        response_text = await self.backup_provider.generate_response(
                            history=history,
                            system_prompt=system_prompt
                        )
                    except Exception as e_local:
                        error_msg = f"System Critical Failure: All cognitive cores offline. ({e_local})"
                        logging.error(error_msg)
                        response_text = error_msg

                # NOTE: Agent responses are saved in TelegramSender after successful send (First Stream)

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
