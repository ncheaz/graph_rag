"""
Data models for the extraction module.

Defines the structure for extracted component data and knowledge graph results.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel, Field


class ComponentMetadata(BaseModel):
    """Basic metadata extracted from component pages."""
    name: str
    title: str
    url: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    last_modified: Optional[datetime] = None


class ComponentProperty(BaseModel):
    """A configurable property of a component."""
    name: str
    description: str
    type: str
    default_value: Optional[str] = None
    required: bool = False
    options: List[str] = Field(default_factory=list)


class UsageGuideline(BaseModel):
    """Usage guideline or best practice for a component."""
    title: str
    description: str
    type: str  # e.g., "do", "don't", "best_practice"
    priority: str = "normal"  # "high", "normal", "low"


class CodeExample(BaseModel):
    """Code example showing component usage."""
    title: str
    code: str
    language: str = "typescript"
    description: Optional[str] = None


class ComponentDependency(BaseModel):
    """Dependency relationship between components."""
    source: str
    target: str
    relationship_type: str  # e.g., "depends_on", "extends", "imports"
    description: Optional[str] = None


class ExtractedComponent(BaseModel):
    """Complete extracted data for a single component."""
    metadata: ComponentMetadata
    properties: List[ComponentProperty] = Field(default_factory=list)
    guidelines: List[UsageGuideline] = Field(default_factory=list)
    examples: List[CodeExample] = Field(default_factory=list)
    dependencies: List[ComponentDependency] = Field(default_factory=list)
    raw_content: str = ""
    extraction_timestamp: datetime = Field(default_factory=datetime.now)


class KGEntity(BaseModel):
    """Knowledge graph entity (node)."""
    id: str
    type: str  # COMPONENT, PROPERTY, VALUE_OPTION, etc.
    properties: Dict[str, Any] = Field(default_factory=dict)

    def dict(self, **kwargs):
        return {
            "id": self.id,
            "type": self.type,
            "properties": self.properties
        }


class KGRelation(BaseModel):
    """Knowledge graph relation (edge)."""
    source_id: str
    target_id: str
    relation_type: str  # HAS_PROPERTY, HAS_OPTION, etc.
    properties: Dict[str, Any] = Field(default_factory=dict)

    def dict(self, **kwargs):
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "properties": self.properties
        }


class KGResult(BaseModel):
    """Result from knowledge graph extraction."""
    entities: List[KGEntity] = Field(default_factory=list)
    relations: List[KGRelation] = Field(default_factory=list)
    source_component: str = ""
    extraction_metadata: Dict[str, Any] = Field(default_factory=dict)

    def dict(self, **kwargs):
        return {
            "entities": [e.dict() for e in self.entities],
            "relations": [r.dict() for r in self.relations],
            "source_component": self.source_component,
            "extraction_metadata": self.extraction_metadata
        }


# Legacy alias for backward compatibility
ComponentData = ExtractedComponent
