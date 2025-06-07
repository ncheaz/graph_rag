from typing import List, Optional
from pydantic import BaseModel
import re

class DiscoveryConfig(BaseModel):
    """Configuration for component discovery on a specific Storybook website."""
    
    # CSS selectors for finding documentation links and components
    component_selectors: List[str] = [
        '#storybook-explorer-tree a[href]',
        '#storybook-explorer-tree button',
        '.sidebar-item[data-nodetype="document"] a',
        '.sidebar-item[data-nodetype="story"] a',
        '.sidebar-item[data-nodetype="component"] button',
        '.sidebar-item button[role="button"]'
    ]
    
    # Optional: XPath patterns for components
    xpath_patterns: Optional[List[str]] = None
    
    # Regex patterns for component URLs
    url_patterns: List[str] = [
        r'/docs/',
        r'/story/'
    ]
    
    # Other site-specific discovery parameters
    discovery_timeout: int = 30  # seconds
    max_components: Optional[int] = None
    
    # Storybook-specific settings
    content_iframe_id: str = "storybook-preview-iframe"
    explorer_tree_id: str = "storybook-explorer-menu"