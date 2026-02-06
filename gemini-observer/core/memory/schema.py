from typing import List

class GraphSchema:
    """
    Defines the Schema and Constraints for the FalkorDB Knowledge Graph.
    This ensures data integrity across all streams.
    """
    
    GRAPH_NAME = "GeminiMemory"
    
    # Structured Constraints for GRAPH.CONSTRAINT command
    # Format: (label, property)
    CONSTRAINTS = [
        # User
        ("User", "telegram_id"),
        ("User", "id"),
        
        # Chat
        ("Chat", "chat_id"),
        ("Chat", "id"),
        
        # Message
        ("Message", "uid"),
        ("Message", "name"),
        
        # Agent
        ("Agent", "telegram_id"),
        
        # Day
        ("Day", "date")
    ]

    @staticmethod
    def get_constraints() -> List[tuple]:
        return GraphSchema.CONSTRAINTS
