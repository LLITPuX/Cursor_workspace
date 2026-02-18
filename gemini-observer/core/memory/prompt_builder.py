"""
GraphPromptBuilder — Dynamic prompt generation from FalkorDB Graph.

Reads Role, Task, Instruction, and Rule nodes from the GeminiStream graph
and assembles system prompts dynamically.

Graph Schema (GeminiStream):
  (:Role)-[:RESPONSIBLE_FOR]->(:Task)-[:FOLLOWS_PROTOCOL]->(:Instruction)
  (:Rule) — standalone rules applied across roles
"""

import logging
import redis.asyncio as redis

logger = logging.getLogger(__name__)

GRAPH_NAME = "GeminiStream"


class GraphPromptBuilder:
    """
    Builds dynamic system prompts by querying the FalkorDB context graph.
    
    Replaces hardcoded prompts in core/prompts.py with graph-driven generation.
    Each stream (Thinker, Analyst, Responder) gets its prompt assembled from:
      - Role description
      - Tasks (via RESPONSIBLE_FOR)
      - Instructions/Protocols (via FOLLOWS_PROTOCOL)
      - Global Rules
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client

    async def _query(self, query: str) -> list:
        """Execute a Cypher query against the GeminiStream graph."""
        try:
            result = await self.redis_client.execute_command(
                "GRAPH.QUERY", GRAPH_NAME, query
            )
            # FalkorDB returns: [headers, rows, stats]
            if result and len(result) >= 2:
                rows = result[1]
                return rows
            return []
        except Exception as e:
            logger.error(f"GraphPromptBuilder query error: {e}")
            return []

    async def _get_role_info(self, role_name: str) -> dict:
        """Fetch role description from graph."""
        rows = await self._query(
            f"MATCH (r:Role {{name: '{role_name}'}}) "
            f"RETURN r.name, r.description"
        )
        if rows:
            row = rows[0]
            return {
                "name": row[0].decode() if isinstance(row[0], bytes) else row[0],
                "description": row[1].decode() if isinstance(row[1], bytes) else row[1]
            }
        return {}

    async def _get_tasks(self, role_name: str) -> list:
        """Fetch tasks assigned to a role (Role->RESPONSIBLE_FOR->Task)."""
        rows = await self._query(
            f"MATCH (:Role {{name: '{role_name}'}})-[:RESPONSIBLE_FOR]->(t:Task) "
            f"RETURN t.name, t.description"
        )
        tasks = []
        for row in rows:
            tasks.append({
                "name": row[0].decode() if isinstance(row[0], bytes) else row[0],
                "description": row[1].decode() if isinstance(row[1], bytes) else row[1]
            })
        return tasks

    async def _get_instructions(self, role_name: str) -> list:
        """Fetch instructions via Task->FOLLOWS_PROTOCOL->Instruction chain."""
        rows = await self._query(
            f"MATCH (:Role {{name: '{role_name}'}})-[:RESPONSIBLE_FOR]->(:Task)"
            f"-[:FOLLOWS_PROTOCOL]->(i:Instruction) "
            f"RETURN i.name, i.content"
        )
        instructions = []
        for row in rows:
            instructions.append({
                "name": row[0].decode() if isinstance(row[0], bytes) else row[0],
                "content": row[1].decode() if isinstance(row[1], bytes) else row[1]
            })
        return instructions

    async def _get_rules(self, role_name: str = None) -> list:
        """Fetch rules for a specific role (via GOVERNED_BY) or all rules."""
        if role_name:
            rows = await self._query(
                f"MATCH (:Role {{name: '{role_name}'}})-[:GOVERNED_BY]->(r:Rule) "
                f"RETURN r.name, r.content"
            )
        else:
            rows = await self._query(
                "MATCH (r:Rule) RETURN r.name, r.content"
            )
        rules = []
        for row in rows:
            rules.append({
                "name": row[0].decode() if isinstance(row[0], bytes) else row[0],
                "content": row[1].decode() if isinstance(row[1], bytes) else row[1]
            })
        return rules

    async def build_system_prompt(self, role_name: str) -> str:
        """
        Build a complete system prompt for a given role from the graph.
        
        Assembles: Role Info + Tasks + Instructions + Rules
        
        Args:
            role_name: Name of the role node (e.g. "Thinker", "Analyst", "Responder")
            
        Returns:
            Assembled system prompt string.
        """
        role_info = await self._get_role_info(role_name)
        tasks = await self._get_tasks(role_name)
        instructions = await self._get_instructions(role_name)
        rules = await self._get_rules(role_name)

        parts = []

        # Role Header
        if role_info:
            parts.append(f"# Role: {role_info.get('name', role_name)}")
            desc = role_info.get('description', '')
            if desc:
                parts.append(f"{desc}\n")

        # Tasks Section
        if tasks:
            parts.append("## Tasks:")
            for t in tasks:
                name = t.get('name', '')
                desc = t.get('description', '')
                parts.append(f"- **{name}**: {desc}")
            parts.append("")

        # Instructions Section
        if instructions:
            parts.append("## Protocol:")
            for instr in instructions:
                name = instr.get('name', '')
                content = instr.get('content', '')
                parts.append(f"### {name}")
                parts.append(f"{content}\n")

        # Rules Section
        if rules:
            parts.append("## Rules:")
            for rule in rules:
                name = rule.get('name', '')
                content = rule.get('content', '')
                parts.append(f"- **{name}**: {content}")
            parts.append("")

        prompt = "\n".join(parts)
        
        if not prompt.strip():
            logger.warning(f"GraphPromptBuilder: Empty prompt for role '{role_name}'. "
                          f"Falling back to minimal prompt.")
            prompt = f"You are the {role_name}. Process the input accordingly."

        logger.info(f"📋 Built prompt for '{role_name}': {len(prompt)} chars")
        return prompt

    async def build_narrative_prompt(
        self, 
        current_message: str, 
        chat_history: list, 
        active_topics: list = None,
        entity_types: list = None,
        recent_thougths: list = None,
        weekly_summaries: list = None
    ) -> str:
        """
        Build prompt for the Thinker (Stream 2) to perform Semantic Analysis.
        """
        system_prompt = await self.build_system_prompt("Thinker")
        
        # Format Contexts
        history_str = "\n".join(
            [f"[{msg.get('time', '')}] {msg.get('author', '?')}: {msg.get('text', '')}" 
             for msg in chat_history]
        )

        topics_str = "None"
        if active_topics:
            topics_str = "\n".join([f"- {t['title']}: {t['description']}" for t in active_topics])

        entities_str = ", ".join(entity_types) if entity_types else "None"

        thoughts_str = "None"
        if recent_thougths:
            thoughts_str = "\n".join([f"- {t[:100]}..." for t in recent_thougths])
            
        summaries_str = "None"
        if weekly_summaries:
            summaries_str = "\n".join([f"- {s[:200]}..." for s in weekly_summaries])

        user_prompt = f"""
CONTEXT:
---
Searchable Entity Types: {entities_str}
---
Active Topics:
{topics_str}
---
Last 7 Days Summaries:
{summaries_str}
---
Recent Thoughts (Do not repeat):
{thoughts_str}
---
Chat History (Last 5 messages):
{history_str}
---

NEW MESSAGE:
{current_message}

INSTRUCTION:
Analyze the "NEW MESSAGE" based on the Protocol. 
Return ONLY VALID JSON.
"""
        return system_prompt + "\n\n" + user_prompt

    async def build_analyst_prompt(self, narrative: str, original_text: str, prev_analyses: list = None) -> str:
        """
        Build prompt for the Analyst (Stream 3) to determine intent and strategy.
        Uses graph-driven system context + runtime data + previous analyses for the day.
        """
        system_prompt = await self.build_system_prompt("Analyst")

        # Previous analyses context
        prev_context = ""
        if prev_analyses:
            prev_parts = []
            for snap in prev_analyses:
                intent = snap.get('intent', '?')
                analysis = snap.get('analysis', '')
                prev_parts.append(f"- [{intent}] {analysis[:100]}")
            prev_context = f"\n\nPrevious Analyses Today:\n" + "\n".join(prev_parts)

        user_prompt = f"""Narrative: {narrative}
Original Input: {original_text}{prev_context}

Possible Intents:
- QUESTION (Needs information search)
- COMMAND (Needs action execution)
- CHAT (Casual conversation)
- IGNORE (Noise, irrelevant)

Output Format:
Provide a reasoning followed by the Intent and a list of abstract tasks (SEARCH, REPLY, EXECUTE).
Example: "User is asking about weather. Intent: QUESTION. Tasks: [SEARCH, REPLY]"
"""

        return system_prompt + "\n\n---\n\n" + user_prompt

    async def build_responder_prompt(self, chat_history: list = None, rag_context: str = "") -> str:
        """
        Build prompt for the Responder (Stream 5) to generate the final response.
        Uses graph-driven persona + runtime context.
        """
        system_prompt = await self.build_system_prompt("Responder")

        if rag_context:
            system_prompt += f"\n\n[ЗНАЙДЕНО В БАЗІ ЗНАНЬ]:\n{rag_context}"

        return system_prompt
