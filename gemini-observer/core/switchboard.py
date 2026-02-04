"""
Switchboard - Provider Management with Fallback Logic.

Manages three providers:
- primary (Gemini): Main cloud intelligence
- fallback (OpenAI): Backup when Gemini 429
- fast (Ollama): Local for quick responses

Logs all fallback events to FalkorDB graph.
"""

import logging
from typing import List, Dict, Any, Optional

from core.llm_interface import LLMProvider, ProviderResponse, RateLimitError


class Switchboard:
    """
    Комутатор провайдерів з автоматичним Fallback та логуванням у граф.
    
    Architecture Directive:
    - Кожен Fallback створює вузол (:SystemEvent) у графі
    - Це дозволяє аналізувати стабільність системи
    """
    
    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider,
        fast: LLMProvider,
        graph_logger = None  # FalkorDBProvider with log_system_event()
    ):
        """
        Args:
            primary: Main provider (Gemini)
            fallback: Backup provider (OpenAI)
            fast: Local fast provider (Ollama)
            graph_logger: FalkorDB instance for logging system events
        """
        self.primary = primary
        self.fallback = fallback
        self.fast = fast
        self.graph = graph_logger
        
        logging.info(
            f"Switchboard initialized: "
            f"primary={primary.get_provider_name()}, "
            f"fallback={fallback.get_provider_name()}, "
            f"fast={fast.get_provider_name()}"
        )
    
    async def generate(
        self,
        history: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        use_fast: bool = False
    ) -> ProviderResponse:
        """
        Generates response with automatic fallback.
        
        Args:
            history: Conversation history
            system_prompt: Optional system prompt
            use_fast: If True, use Ollama directly (for Gatekeeper etc.)
            
        Returns:
            ProviderResponse from successful provider
        """
        # Fast path - use local Ollama
        if use_fast:
            logging.info("Switchboard: Using FAST provider (Ollama)")
            return await self.fast.generate_response(history, system_prompt)
        
        # Primary path - try Gemini first
        try:
            logging.info("Switchboard: Trying PRIMARY provider (Gemini)")
            return await self.primary.generate_response(history, system_prompt)
            
        except RateLimitError as e:
            logging.warning(f"Switchboard: PRIMARY failed with RateLimitError: {e}")
            
            # Log fallback event to graph
            await self._log_fallback_event(
                from_provider=self.primary.get_provider_name(),
                to_provider=self.fallback.get_provider_name(),
                reason=str(e)
            )
            
            # Try fallback (OpenAI)
            try:
                logging.info("Switchboard: Trying FALLBACK provider (OpenAI)")
                return await self.fallback.generate_response(history, system_prompt)
                
            except RateLimitError as e2:
                logging.error(f"Switchboard: FALLBACK also failed: {e2}")
                
                # Last resort - use local Ollama
                await self._log_fallback_event(
                    from_provider=self.fallback.get_provider_name(),
                    to_provider=self.fast.get_provider_name(),
                    reason=str(e2)
                )
                
                logging.info("Switchboard: Last resort - using FAST provider")
                return await self.fast.generate_response(history, system_prompt)
    
    async def _log_fallback_event(
        self,
        from_provider: str,
        to_provider: str,
        reason: str
    ):
        """
        Logs fallback event to FalkorDB graph as (:SystemEvent).
        
        Cypher created:
        CREATE (:SystemEvent {
            type: 'FALLBACK',
            from_provider: 'gemini',
            to_provider: 'openai',
            reason: '429_quota',
            timestamp: datetime()
        })
        """
        if self.graph and hasattr(self.graph, 'log_system_event'):
            try:
                await self.graph.log_system_event(
                    event_type="FALLBACK",
                    source=from_provider,
                    severity="warning",
                    details=f"Switched from {from_provider} to {to_provider}: {reason}"
                )
                logging.info(f"Switchboard: Logged FALLBACK event to graph")
            except Exception as e:
                logging.error(f"Switchboard: Failed to log to graph: {e}")
        else:
            logging.warning("Switchboard: No graph_logger available for FALLBACK event")
