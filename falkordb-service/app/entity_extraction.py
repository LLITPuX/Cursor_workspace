"""Entity extraction service using GLINER v2.1"""
from typing import List, Optional
from gliner import GLiNER
from app.models.response import EntityModel
import logging
import torch

logger = logging.getLogger(__name__)

# Типи сутностей для запитів користувача
QUERY_ENTITY_TYPES = [
    "Technology", "Framework", "Library", "Database", "Language",
    "Project", "Component", "Service", "API", "Endpoint",
    "Task", "Feature", "Bug", "Requirement",
    "Concept", "Pattern", "Architecture", "Design",
    "Person", "Role", "Team",
    "File", "Directory", "Config", "Script",
    "Preference", "Constraint", "Decision"
]

# Розширений список для відповідей агента
RESPONSE_ENTITY_TYPES = QUERY_ENTITY_TYPES + [
    "Tool",           # read_file, codebase_search, тощо
    "CodeBlock",      # блоки коду
    "Recommendation", # рекомендації
    "Action",         # виконані дії
    "Analysis",       # аналіз ситуації
    "Question"       # питання для уточнення
]


class EntityExtractor:
    """Entity extraction using GLINER v2.1"""
    
    def __init__(self, model_name: str = "urchade/gliner_medium-v2.1"):
        """
        Initialize GLINER model
        
        Args:
            model_name: GLINER model name from Hugging Face
                       Options: 
                       - "urchade/gliner_medium-v2.1" (default, balanced)
                       - "urchade/gliner_small-v2.1" (faster)
                       - "urchade/gliner_base-v2.1" (smallest)
        """
        self.model_name = model_name
        self.model = None
        self.device = 0 if torch.cuda.is_available() else -1
        logger.info(f"Initializing GLINER entity extractor with model {model_name} on device {self.device}")
        self._load_model()
    
    def _load_model(self):
        """Load GLINER model"""
        try:
            logger.info(f"Loading GLINER model: {self.model_name}")
            self.model = GLiNER.from_pretrained(self.model_name)
            logger.info(f"GLINER model {self.model_name} loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load GLINER model: {e}")
            raise
    
    def extract(
        self, 
        text: str, 
        entity_types: List[str], 
        threshold: float = 0.5
    ) -> List[EntityModel]:
        """
        Extract entities from text using GLINER
        
        Args:
            text: Text to extract entities from
            entity_types: List of entity types to look for
            threshold: Confidence threshold for entity extraction (0.0-1.0)
            
        Returns:
            List of EntityModel objects
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for entity extraction")
            return []
        
        if not entity_types:
            logger.warning("No entity types provided for extraction")
            return []
        
        try:
            # GLINER extraction
            entities = self.model.predict_entities(
                text,
                entity_types,
                threshold=threshold
            )
            
            # Convert to EntityModel format
            result = []
            for entity in entities:
                # GLINER returns: {"text": "...", "label": "...", "start": int, "end": int, "score": float}
                result.append(EntityModel(
                    text=entity.get("text", ""),
                    type=entity.get("label", ""),
                    start=entity.get("start", 0),
                    end=entity.get("end", 0)
                ))
            
            logger.debug(f"Extracted {len(result)} entities from text (length: {len(text)})")
            return result
            
        except Exception as e:
            logger.error(f"Entity extraction error: {e}", exc_info=True)
            return []


# Singleton instances (lazy loading)
_query_extractor: Optional[EntityExtractor] = None
_response_extractor: Optional[EntityExtractor] = None


def get_query_extractor() -> EntityExtractor:
    """Get extractor instance for user queries"""
    global _query_extractor
    if _query_extractor is None:
        _query_extractor = EntityExtractor()
    return _query_extractor


def get_response_extractor() -> EntityExtractor:
    """Get extractor instance for assistant responses"""
    global _response_extractor
    if _response_extractor is None:
        _response_extractor = EntityExtractor()
    return _response_extractor
