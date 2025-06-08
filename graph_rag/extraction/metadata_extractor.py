"""
Metadata extractor for component HTML content.

Uses CSS selectors and XPath for precise field extraction from Storybook pages.
Supports multi-source metadata aggregation from main page and iframe content.
"""

import re
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from bs4 import BeautifulSoup, Tag
from .data_models import ComponentMetadata


class MetadataExtractor:
    """Extracts structured metadata from component HTML using CSS selectors."""
    
    # Default selectors for common Storybook elements
    DEFAULT_SELECTORS = {
        "title": [
            "h1",
            ".sb-heading",
            "[data-testid='title']",
            ".docs-title"
        ],
        "description": [
            ".docs-description",
            ".sb-description", 
            "p:first-of-type",
            "[data-testid='description']"
        ],
        "category": [
            ".docs-category",
            ".sb-category",
            "[data-category]"
        ],
        "tags": [
            ".docs-tags .tag",
            ".sb-tags .tag",
            "[data-tags]"
        ]
    }
    
    @staticmethod
    def extract(soup: BeautifulSoup, 
                fields: List[str], 
                selectors: Optional[Dict[str, Union[str, List[str]]]] = None) -> Dict[str, Any]:
        """
        Extracts metadata using field-specific selectors.
        
        Args:
            soup: Parsed HTML document
            fields: Metadata fields to extract
            selectors: CSS selectors for each field (uses defaults if not provided)
            
        Returns:
            Dictionary of field-value pairs
        """
        if selectors is None:
            selectors = {}
            
        result = {}
        
        for field in fields:
            # Get selectors for this field (default or custom)
            field_selectors = selectors.get(field, MetadataExtractor.DEFAULT_SELECTORS.get(field, []))
            if isinstance(field_selectors, str):
                field_selectors = [field_selectors]
                
            value = MetadataExtractor._extract_field_value(soup, field, field_selectors)
            if value is not None:
                result[field] = value
                
        return result
        
    @staticmethod
    def _extract_field_value(soup: BeautifulSoup, field: str, selectors: List[str]) -> Optional[Any]:
        """Extract value for a specific field using provided selectors."""
        for selector in selectors:
            try:
                elements = soup.select(selector)
                if not elements:
                    continue
                    
                if field == "tags":
                    # Tags are typically multiple elements
                    return [MetadataExtractor._clean_text(el.get_text()) for el in elements]
                elif field in ["title", "description", "category"]:
                    # Text fields - take first non-empty match
                    for element in elements:
                        text = MetadataExtractor._clean_text(element.get_text())
                        if text:
                            return text
                else:
                    # Generic text extraction
                    text = MetadataExtractor._clean_text(elements[0].get_text())
                    if text:
                        return text
                        
            except Exception:
                # Continue to next selector if this one fails
                continue
                
        return None
        
    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ""
            
        # Remove extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common Storybook artifacts
        cleaned = re.sub(r'⋅ Storybook$', '', cleaned)
        cleaned = re.sub(r'^API \/ ', '', cleaned)
        
        return cleaned.strip()
        
    @staticmethod
    def extract_component_metadata(html_content: str, 
                                 name: str, 
                                 url: str,
                                 custom_selectors: Optional[Dict[str, Union[str, List[str]]]] = None) -> ComponentMetadata:
        """
        Extract complete component metadata from HTML content.
        
        Args:
            html_content: Raw HTML content
            name: Component name from crawler
            url: Component URL
            custom_selectors: Custom CSS selectors for specific fields
            
        Returns:
            ComponentMetadata object with extracted information
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Define fields to extract
        fields = ["title", "description", "category", "tags"]
        
        # Extract metadata
        extracted = MetadataExtractor.extract(soup, fields, custom_selectors)
        
        # Build ComponentMetadata object
        return ComponentMetadata(
            name=name,
            title=extracted.get("title", name),  # Fall back to name if no title
            url=url,
            description=extracted.get("description"),
            category=extracted.get("category"),
            tags=extracted.get("tags", []),
            last_modified=datetime.now()
        )
        
    @staticmethod
    def extract_from_iframe(soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract metadata specifically from Storybook iframe content.
        
        Args:
            soup: Parsed HTML document
            
        Returns:
            Dictionary of extracted iframe-specific metadata
        """
        iframe_data = {}
        
        # Look for Storybook-specific elements in iframe
        iframe_selectors = {
            "component_props": [
                ".sb-argstableBlock tbody tr",
                ".docblock-argstable tbody tr"
            ],
            "controls": [
                ".sb-argstableBlock-body button",
                ".docblock-argstable button"
            ],
            "canvas_content": [
                "#storybook-root",
                ".sb-show-main"
            ]
        }
        
        for field, selectors in iframe_selectors.items():
            value = MetadataExtractor._extract_field_value(soup, field, selectors)
            if value is not None:
                iframe_data[field] = value
                
        return iframe_data
        
    @staticmethod
    def extract_properties_table(soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        Extract component properties from Storybook args table.
        
        Args:
            soup: Parsed HTML document
            
        Returns:
            List of property dictionaries
        """
        properties = []
        
        # Find the args table
        table_selectors = [
            ".sb-argstableBlock tbody tr",
            ".docblock-argstable tbody tr",
            "table[aria-label*='args'] tbody tr"
        ]
        
        for selector in table_selectors:
            rows = soup.select(selector)
            if not rows:
                continue
                
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:  # Minimum: name, description, default
                    prop = {
                        'name': MetadataExtractor._clean_text(cells[0].get_text()),
                        'description': MetadataExtractor._clean_text(cells[1].get_text()),
                        'default': MetadataExtractor._clean_text(cells[2].get_text()) if len(cells) > 2 else None,
                        'control': MetadataExtractor._clean_text(cells[3].get_text()) if len(cells) > 3 else None
                    }
                    
                    # Check if property is required
                    if '*' in cells[0].get_text() or 'required' in cells[0].get('class', []):
                        prop['required'] = True
                        
                    properties.append(prop)
                    
            # If we found properties, break (don't try other selectors)
            if properties:
                break
                
        return properties
