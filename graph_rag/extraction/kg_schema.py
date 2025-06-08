"""
Custom knowledge graph schema validator for LlamaIndex integration.
Handles validation of the KG schema separately from Pydantic.
"""

from typing import List, Tuple, Dict, Any, Sequence

class KGSchemaValidator:
    """Validates knowledge graph schema definitions."""
    
    def __init__(self,
                entities: Sequence[Tuple[str, str]],
                relations: Sequence[Tuple[str, str, str, str]]):
        self.entities = entities
        self.relations = relations
        
    def validate(self) -> bool:
        """Validate the schema structure."""
        if not all(isinstance(e, tuple) and len(e) == 2 for e in self.entities):
            raise ValueError("Entities must be tuples of (type, description)")
            
        if not all(isinstance(r, tuple) and len(r) == 4 for r in self.relations):
            raise ValueError("Relations must be tuples of (type, source, target, description)")
            
        return True
        
    def get_entity_types(self) -> List[str]:
        """Get list of entity types."""
        return [e[0] for e in self.entities]
        
    def get_relation_types(self) -> List[str]:
        """Get list of relation types."""
        return [r[0] for r in self.relations]