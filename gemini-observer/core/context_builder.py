"""
Context Builder - Dynamic Prompt Assembly Module.

This module connects to the Knowledge Graph to fetch Agent Persona, Role, Task, 
Protocols, Instructions, and Rules to assemble a coherent System Prompt "on the fly".

Graph Schema Traversal:
(Agent)-[:PLAYS_ROLE]->(Role)-[:RESPONSIBLE_FOR]->(Task)-[:FOLLOWS_PROTOCOL]->(Protocol)-[:COMPOSED_OF]->(Instruction)-[:ENFORCES]->(Rule)
""",

import logging
from typing import List, Dict, Optional
import os
from datetime import datetime

from memory.falkordb import FalkorDBProvider
import json

class ContextBuilder:
    """
    Constructs dynamic system prompts from Graph Context.
    """
    
    def __init__(self, memory: FalkorDBProvider):
        self.memory = memory
        self.debug_dir = "debug/prompts"
        
        # Ensure debug directory exists
        os.makedirs(self.debug_dir, exist_ok=True)

    async def build_gatekeeper_prompt(
        self,
        chat_context: List[Dict[str, str]],
        current_message_text: str
    ) -> str:
        """
        Builds the specific prompt for the Gatekeeper (Classification) task.
        """
        return await self._build_prompt_from_graph(
            role_name="Gatekeeper", 
            task_name="Triage Message",
            context=chat_context,
            current_message=current_message_text
        )

    async def _build_prompt_from_graph(
        self,
        role_name: str,
        task_name: str,
        context: List[Dict[str, str]],
        current_message: str
    ) -> str:
        """
        Generic builder for any Role/Task pair.
        """
        query = f"""
        MATCH (r:Role {{name: '{role_name}'}})
        MATCH (r)-[:RESPONSIBLE_FOR]->(t:Task {{name: '{task_name}'}})
        
        // Optional Protocol
        OPTIONAL MATCH (t)-[:FOLLOWS_PROTOCOL]->(p:Protocol)
        
        // Optional Instruction
        OPTIONAL MATCH (p)-[:COMPOSED_OF]->(i:Instruction)
        
        // Rules (can be multiple)
        OPTIONAL MATCH (i)-[:ENFORCES]->(rule:Rule)
        
        RETURN 
            r.name as role, 
            t.description as task_desc,
            p.description as protocol,
            i.text as instruction,
            rule.text as rule_text
        """
        
        try:
            result = await self.memory._query(query)
            
            if not result or len(result) < 2 or not result[1]:
                logging.error(f"ContextBuilder: No graph nodes found for {role_name}/{task_name}")
                return self._fallback_gatekeeper_prompt(context, current_message)
            
            # Helper to decode
            def dec(x): return x.decode('utf-8') if isinstance(x, bytes) else (x or "")
            
            # Parse First Row for Context Containers (Role, Task, Protocol, Instruction)
            # These are 1:1 for this builder
            first_row = result[1][0]
            role = dec(first_row[0])
            task_desc = dec(first_row[1])
            protocol = dec(first_row[2])
            instruction = dec(first_row[3]).replace("\\QS_", '"')
            
            # Collect Rules from ALL rows (1:N relationship)
            rules = []
            for row in result[1]:
                r_text = dec(row[4]).replace("\\QS_", '"')
                if r_text:  # Filter out None/Empty if OPTIONAL MATCH matched nothing
                    rules.append(r_text)
            
            # Deduplicate rules just in case
            rules = list(dict.fromkeys(rules))
            
            # ══════════════════════════════════════════════════════════════
            # ASSEMBLY
            # ══════════════════════════════════════════════════════════════
            
            prompt_parts = []
            
            # 1. HEADER (Role)
            prompt_parts.append(f"ROLE: {role}")
            prompt_parts.append("IDENTITY: You are 'Bober Sikfan'. Messages addressed to 'Bober Sikfan' are addressed to YOU.")
            
            # 2. TASK
            if task_desc:
                prompt_parts.append(f"TASK: {task_desc}")
            
            # 3. PROTOCOL (High level steps)
            if protocol:
                prompt_parts.append(f"\nPROTOCOL:\n{protocol}")
                
            # 4. INSTRUCTION (Specific actions)
            if instruction:
                prompt_parts.append(f"\nINSTRUCTION:\n{instruction}")
                
            # 5. RULES (Constraints)
            if rules:
                prompt_parts.append("\nRULES:")
                for rule in rules:
                    prompt_parts.append(f"- {rule}")
            
            # 6. CONTEXT (Chat History)
            prompt_parts.append("\nCONTEXT (Last 20 messages):")
            history_text = self._format_history(context)
            prompt_parts.append(history_text)
            
            # 7. CURRENT MESSAGE
            prompt_parts.append(f"\nMESSAGE TO ANALYZE:\n{current_message}")
            
            # 8. RESPONSE FORMAT (JSON) check
            if "JSON" not in instruction and "JSON" not in str(rules):
                 prompt_parts.append("\nIMPORTANT: Output strictly valid JSON.")

            final_prompt = "\n".join(prompt_parts)
            return final_prompt

        except Exception as e:
            logging.error(f"ContextBuilder Error: {e}")
            return self._fallback_gatekeeper_prompt(context, current_message)

    def _format_history(self, messages: List[Dict[str, str]]) -> str:
        if not messages:
            return "(No recent messages)"
            
        lines = []
        for msg in messages:
            author = msg.get('author', '?')
            text = msg.get('text', '')
            time = msg.get('time', '')
            lines.append(f"[{time}] {author}: {text}")
        return "\n".join(lines)

    def _fallback_gatekeeper_prompt(self, context, current_message) -> str:
        """Fallback if graph is unreachable"""
        logging.warning("ContextBuilder: Using FALLBACK prompt")
        hist = self._format_history(context)
        return f"""
        ACT AS: Gatekeeper
        TASK: Process usage.
        OUTPUT: JSON {{ "target":"DIRECT" }}
        
        CONTEXT:
        {hist}
        
        MESSAGE:
        {current_message}
        """

    def save_debug_prompt(self, prompt: str, response: str, suffix: str = ""):
        """Save prompt and response to local file for debugging (JSON format)."""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.debug_dir}/prompt_{ts}_{suffix}.json"
            
            data = {
                "timestamp": ts,
                "suffix": suffix,
                "prompt": prompt,
                "response_raw": response
            }
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logging.info(f"💾 Saved debug prompt to {filename}")
        except Exception as e:
            logging.error(f"Failed to save debug prompt: {e}")
