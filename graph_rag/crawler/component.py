from pydantic import BaseModel
from typing import List, Dict, Any

class Component(BaseModel):
    """Represents a design system component."""
    name: str
    url: str
    selectors: List[str]
    metadata: Dict[str, Any] = {}