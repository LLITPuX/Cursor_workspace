"""
Researcher - Agentic RAG with Cypher Query Tool.

This module provides tool integration for Gemini/OpenAI to execute
Cypher queries against FalkorDB, enabling agentic RAG capabilities.

Flow:
1. Analyst generates search_query from message
2. Researcher receives search_query
3. Researcher asks LLM to formulate Cypher query
4. Execute query against FalkorDB
5. LLM interprets results and generates response
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from core.llm_interface import ProviderResponse
from core.switchboard import Switchboard


@dataclass
class QueryResult:
    """Result of a Cypher query execution."""
    success: bool
    data: List[Dict[str, Any]]
    error: Optional[str] = None
    query: Optional[str] = None


class Researcher:
    """
    Agentic RAG: Allows LLM to query the Knowledge Graph.
    
    Provides `query_graph` tool that:
    1. Takes a natural language question
    2. LLM formulates Cypher query
    3. Executes against FalkorDB
    4. Returns structured results
    """
    
    # Prompt for Cypher query generation
    CYPHER_PROMPT = """Ти — експерт з Cypher (мова запитів для графових баз даних FalkorDB/Neo4j).

Граф GeminiMemory має таку схему:
- (:User {telegram_id, name}) — користувачі
- (:Agent {telegram_id, name}) — боти
- (:Chat {chat_id, name}) — чати
- (:Message {uid, text, created_at, name}) — повідомлення
- (:Thought {topic, new_facts, target_user}) — аналітичні вузли
- (:Day {date}) — дні
- (:SystemEvent {type, source, details}) — системні події

Зв'язки:
- [:AUTHORED] — User→Message
- [:GENERATED] — Agent→Message  
- [:HAPPENED_IN] — Message→Chat
- [:HAPPENED_AT] — Message→Day
- [:NEXT] — Message→Message (хронологія)
- [:DERIVED_FROM] — Thought→Message

Сформуй Cypher-запит для наступного питання.
ВАЖЛИВО:
1. Використовуй SEARCH (CONTAINS) по ключовим словам, а не цілим фразам.
2. Якщо запит однією мовою, а в базі може бути інша — шукай обома мовами (Укр/Рос).
   Наприклад: WHERE toLower(m.text) CONTAINS 'їду' OR toLower(m.text) CONTAINS 'еду'
3. Поверни ТІЛЬКИ запит без пояснень.
4. Використовуй LIMIT 10.

Питання: """

    # Prompt for interpreting query results
    INTERPRET_PROMPT = """Ти отримав результати запиту до Графа Знань. 
Інтерпретуй їх та дай коротку відповідь користувачу.

Запит: {query}
Результати: {results}

Відповідь (коротко, по суті):"""

    def __init__(
        self,
        switchboard: Switchboard,
        memory_provider,  # FalkorDBProvider
    ):
        self.switchboard = switchboard
        self.memory = memory_provider
        logging.info("Researcher initialized")

    def _clean_data(self, data: Any) -> Any:
        """Recursively decode bytes and handle graph objects."""
        if isinstance(data, bytes):
            return data.decode('utf-8')
        elif isinstance(data, list):
            return [self._clean_data(item) for item in data]
        elif isinstance(data, dict):
            return {self._clean_data(k): self._clean_data(v) for k, v in data.items()}
        elif hasattr(data, 'properties') and hasattr(data, 'labels'): # Node object
            return {
                "id": getattr(data, 'id', None),
                "labels": getattr(data, 'labels', []),
                "properties": self._clean_data(getattr(data, 'properties', {}))
            }
        elif hasattr(data, 'properties') and hasattr(data, 'relation'): # Edge object
            return {
                "id": getattr(data, 'id', None),
                "type": getattr(data, 'relation', None),
                "properties": self._clean_data(getattr(data, 'properties', {}))
            }
        return data

    async def query_knowledge(self, question: str) -> str:
        """
        Main entry point: Answer a question using the Knowledge Graph.
        
        Args:
            question: Natural language question
            
        Returns:
            Answer string based on graph data
        """
        logging.info(f"🔍 Researcher: Processing question: {question[:50]}...")
        
        # Step 1: Generate Cypher query
        cypher_query = await self._generate_cypher(question)
        
        if not cypher_query:
            return "Не вдалося сформувати запит до бази знань."
        
        logging.info(f"🔍 Researcher: Generated Cypher: {cypher_query[:100]}...")
        
        # Step 2: Execute query
        result = await self._execute_query(cypher_query)
        
        if not result.success:
            logging.warning(f"Researcher: Query failed: {result.error}")
            return f"Помилка запиту: {result.error}"
        
        if not result.data:
            return "В базі знань немає інформації за цим запитом."
        
        logging.info(f"🔍 Researcher: Got {len(result.data)} results")
        
        # Step 3: Interpret results
        answer = await self._interpret_results(cypher_query, result.data)
        
        return answer

    async def _generate_cypher(self, question: str) -> Optional[str]:
        """Generate Cypher query from natural language question."""
        prompt = self.CYPHER_PROMPT + question
        
        try:
            response: ProviderResponse = await self.switchboard.generate(
                history=[{"role": "user", "content": prompt}],
                system_prompt=None,
                use_fast=False  # Use Gemini/OpenAI for better query quality
            )
            
            # Clean response
            query = response.content.strip()
            
            # Remove markdown code blocks if present
            if query.startswith("```"):
                lines = query.split("\n")
                query = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            # Basic validation
            if not any(kw in query.upper() for kw in ["MATCH", "RETURN", "CREATE"]):
                logging.warning(f"Researcher: Invalid Cypher generated: {query}")
                return None
            
            return query.strip()
            
        except Exception as e:
            logging.error(f"Researcher: Failed to generate Cypher: {e}")
            return None

    async def _execute_query(self, cypher_query: str) -> QueryResult:
        """Execute Cypher query against FalkorDB."""
        if not hasattr(self.memory, '_query'):
            return QueryResult(
                success=False,
                data=[],
                error="Memory provider doesn't support _query"
            )
        
        try:
            result = await self.memory._query(cypher_query)
            
            # Parse FalkorDB result format
            # result[0] = headers, result[1] = rows, result[2] = stats
            if not result or len(result) < 2:
                return QueryResult(success=True, data=[], query=cypher_query)
            
            headers = result[0] if result[0] else []
            rows = result[1] if len(result) > 1 else []
            
            # Convert to list of dicts
            # Convert to list of dicts
            data = []
            for row in rows:
                row_dict = {}
                for i, value in enumerate(row):
                    key = headers[i] if i < len(headers) else f"col{i}"
                    # Clean key
                    if isinstance(key, bytes):
                        key = key.decode('utf-8')
                    
                    # Clean value recursively
                    row_dict[key] = self._clean_data(value)
                    
                data.append(row_dict)
            
            return QueryResult(success=True, data=data, query=cypher_query)
            
        except Exception as e:
            logging.error(f"Researcher: Query execution failed: {e}")
            return QueryResult(
                success=False,
                data=[],
                error=str(e),
                query=cypher_query
            )

    async def _interpret_results(
        self, 
        query: str, 
        results: List[Dict[str, Any]]
    ) -> str:
        """Interpret query results and generate human-readable answer."""
        # Limit results for prompt
        results_str = json.dumps(results[:5], ensure_ascii=False, indent=2)
        
        prompt = self.INTERPRET_PROMPT.format(
            query=query,
            results=results_str
        )
        
        try:
            response: ProviderResponse = await self.switchboard.generate(
                history=[{"role": "user", "content": prompt}],
                system_prompt=None,
                use_fast=True  # Use Gemma for faster interpretation
            )
            
            return response.content.strip()
            
        except Exception as e:
            logging.error(f"Researcher: Failed to interpret results: {e}")
            # Fallback: return raw data summary
            return f"Знайдено {len(results)} записів у базі знань."


# ═══════════════════════════════════════════════════════════════════════════
# Tool Definition for OpenAI Function Calling
# ═══════════════════════════════════════════════════════════════════════════

RESEARCHER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_knowledge_graph",
            "description": "Query the FalkorDB knowledge graph to find information about users, messages, events, and relationships. Use this when you need to look up historical information or facts about people.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Natural language question to answer using the knowledge graph"
                    }
                },
                "required": ["question"]
            }
        }
    }
]


class ResearcherToolHandler:
    """
    Handler for processing tool calls from OpenAI/Gemini.
    
    Integrates with chat loop to execute knowledge graph queries
    when LLM requests the query_knowledge_graph tool.
    """
    
    def __init__(self, researcher: Researcher):
        self.researcher = researcher
    
    async def handle_tool_call(
        self, 
        tool_name: str, 
        arguments: Dict[str, Any]
    ) -> str:
        """Handle a tool call from the LLM."""
        if tool_name == "query_knowledge_graph":
            question = arguments.get("question", "")
            return await self.researcher.query_knowledge(question)
        
        return f"Unknown tool: {tool_name}"
    
    def get_tools(self) -> List[Dict]:
        """Get tool definitions for OpenAI function calling."""
        return RESEARCHER_TOOLS
