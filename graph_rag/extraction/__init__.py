"""
Extraction module for processing crawled HTML content into structured knowledge graph data.

This module implements a hybrid extraction approach combining:
- Traditional HTML parsing with BeautifulSoup
- LLM-based semantic analysis with LlamaIndex PropertyGraphIndex
- Schema-guided entity and relationship extraction
"""

from .metadata_extractor import MetadataExtractor
from .content_parser import ContentParser
from .relationship_analyzer import RelationshipAnalyzer
from .kg_extractor import KGExtractor
from .extractor import ExtractionOrchestrator
from .data_models import ComponentData, ExtractedComponent, KGResult

__all__ = [
    "MetadataExtractor",
    "ContentParser", 
    "RelationshipAnalyzer",
    "KGExtractor",
    "ExtractionOrchestrator",
    "ComponentData",
    "ExtractedComponent",
    "KGResult"
]
