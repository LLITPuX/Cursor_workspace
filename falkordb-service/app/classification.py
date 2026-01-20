"""Classification service using DeBERTa v3 for zero-shot classification"""
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from typing import List, Dict, Optional
import logging
import torch

logger = logging.getLogger(__name__)


class BaseClassifier:
    """Base class for text classifiers"""
    
    def __init__(self, model_name: str = "microsoft/deberta-v3-base"):
        """
        Initialize base classifier
        
        Args:
            model_name: Hugging Face model name
        """
        self.model_name = model_name
        self.device = 0 if torch.cuda.is_available() else -1
        logger.info(f"Initializing classifier with model {model_name} on device {self.device}")
        
        try:
            # Use zero-shot classification pipeline
            self.classifier = pipeline(
                "zero-shot-classification",
                model=model_name,
                device=self.device
            )
            logger.info(f"Classifier {model_name} loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load classifier {model_name}: {e}")
            raise
    
    def classify(self, text: str, labels: List[str], multi_label: bool = False) -> Dict:
        """
        Classify text using zero-shot classification
        
        Args:
            text: Text to classify
            labels: List of possible labels
            multi_label: Whether to allow multiple labels
            
        Returns:
            Dictionary with classification results
        """
        if not text.strip():
            logger.warning("Empty text provided for classification")
            return {"label": labels[0] if labels else "unknown", "score": 0.0}
        
        try:
            result = self.classifier(text, labels, multi_label=multi_label)
            return result
        except Exception as e:
            logger.error(f"Classification error: {e}")
            # Fallback to first label
            return {"label": labels[0] if labels else "unknown", "score": 0.0}


class SentimentClassifier(BaseClassifier):
    """Classifier for user query sentiment"""
    
    SENTIMENT_LABELS = [
        "neutral",
        "positive_feedback",
        "negative_feedback",
        "frustrated"
    ]
    
    def __init__(self):
        """Initialize sentiment classifier"""
        super().__init__()
        self.labels = self.SENTIMENT_LABELS
    
    def classify(self, text: str) -> str:
        """
        Classify sentiment of user query
        
        Args:
            text: User query text
            
        Returns:
            Sentiment label: neutral, positive_feedback, negative_feedback, or frustrated
        """
        result = super().classify(text, self.labels, multi_label=False)
        return result.get("label", "neutral")


class IntentClassifier(BaseClassifier):
    """Multi-label classifier for user query intents"""
    
    INTENT_LABELS = [
        "information_seeking",
        "capability_inquiry",
        "task_execution",
        "project_discussion",
        "error_resolution",
        "clarification_needed"
    ]
    
    def __init__(self):
        """Initialize intent classifier"""
        super().__init__()
        self.labels = self.INTENT_LABELS
    
    def classify(self, text: str, threshold: float = 0.3) -> List[str]:
        """
        Classify intents of user query (multi-label)
        
        Args:
            text: User query text
            threshold: Minimum score threshold for including intent
            
        Returns:
            List of intent labels
        """
        result = super().classify(text, self.labels, multi_label=True)
        
        # Extract labels above threshold
        labels = result.get("labels", [])
        scores = result.get("scores", [])
        
        intents = [
            label for label, score in zip(labels, scores)
            if score >= threshold
        ]
        
        # Always return at least one intent
        if not intents and labels:
            intents = [labels[0]]
        
        return intents


class ComplexityClassifier(BaseClassifier):
    """Classifier for query complexity"""
    
    COMPLEXITY_LABELS = [
        "simple_question",
        "structured_prompt",
        "architectural",
        "requires_clarification"
    ]
    
    def __init__(self):
        """Initialize complexity classifier"""
        super().__init__()
        self.labels = self.COMPLEXITY_LABELS
    
    def classify(self, text: str) -> str:
        """
        Classify complexity of user query
        
        Args:
            text: User query text
            
        Returns:
            Complexity label: simple_question, structured_prompt, architectural, or requires_clarification
        """
        result = super().classify(text, self.labels, multi_label=False)
        return result.get("label", "simple_question")


class ResponseTypeClassifier(BaseClassifier):
    """Classifier for assistant response type"""
    
    RESPONSE_TYPE_LABELS = [
        "explanation",
        "code_proposal",
        "analysis",
        "question"
    ]
    
    def __init__(self):
        """Initialize response type classifier"""
        super().__init__()
        self.labels = self.RESPONSE_TYPE_LABELS
    
    def classify(self, text: str) -> str:
        """
        Classify type of assistant response
        
        Args:
            text: Assistant response text
            
        Returns:
            Response type: explanation, code_proposal, analysis, or question
        """
        result = super().classify(text, self.labels, multi_label=False)
        return result.get("label", "explanation")


class ResponseComplexityClassifier(BaseClassifier):
    """Classifier for assistant response complexity"""
    
    COMPLEXITY_LABELS = [
        "simple",
        "detailed",
        "architectural"
    ]
    
    def __init__(self):
        """Initialize response complexity classifier"""
        super().__init__()
        self.labels = self.COMPLEXITY_LABELS
    
    def classify(self, text: str) -> str:
        """
        Classify complexity of assistant response
        
        Args:
            text: Assistant response text
            
        Returns:
            Complexity label: simple, detailed, or architectural
        """
        result = super().classify(text, self.labels, multi_label=False)
        return result.get("label", "simple")


# Singleton instances (lazy loading)
_sentiment_classifier: Optional[SentimentClassifier] = None
_intent_classifier: Optional[IntentClassifier] = None
_complexity_classifier: Optional[ComplexityClassifier] = None
_response_type_classifier: Optional[ResponseTypeClassifier] = None
_response_complexity_classifier: Optional[ResponseComplexityClassifier] = None


def get_sentiment_classifier() -> SentimentClassifier:
    """Get or create sentiment classifier instance"""
    global _sentiment_classifier
    if _sentiment_classifier is None:
        _sentiment_classifier = SentimentClassifier()
    return _sentiment_classifier


def get_intent_classifier() -> IntentClassifier:
    """Get or create intent classifier instance"""
    global _intent_classifier
    if _intent_classifier is None:
        _intent_classifier = IntentClassifier()
    return _intent_classifier


def get_complexity_classifier() -> ComplexityClassifier:
    """Get or create complexity classifier instance"""
    global _complexity_classifier
    if _complexity_classifier is None:
        _complexity_classifier = ComplexityClassifier()
    return _complexity_classifier


def get_response_type_classifier() -> ResponseTypeClassifier:
    """Get or create response type classifier instance"""
    global _response_type_classifier
    if _response_type_classifier is None:
        _response_type_classifier = ResponseTypeClassifier()
    return _response_type_classifier


def get_response_complexity_classifier() -> ResponseComplexityClassifier:
    """Get or create response complexity classifier instance"""
    global _response_complexity_classifier
    if _response_complexity_classifier is None:
        _response_complexity_classifier = ResponseComplexityClassifier()
    return _response_complexity_classifier
