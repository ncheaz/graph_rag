"""
Content parser for extracting component documentation and usage guidelines.

Processes component documentation, extracts code examples, and handles 
dynamic content loaded in Storybook iframe.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup, Tag
from .data_models import UsageGuideline, CodeExample

logger = logging.getLogger(__name__)

class ContentParser:
    """Parses component documentation and extracts structured content."""
    
    # Common code block selectors in Storybook
    CODE_BLOCK_SELECTORS = [
        "pre code",
        ".sb-code",
        ".docs-code",
        "[data-testid='code-block']",
        ".language-typescript",
        ".language-javascript",
        ".language-tsx",
        ".language-jsx"
    ]
    
    # Selectors for documentation sections
    DOCS_SELECTORS = {
        "usage": [
            ".docs-usage",
            ".sb-usage", 
            "[data-section='usage']",
            "h2:contains('Usage') + *",
            "h3:contains('Usage') + *"
        ],
        "guidelines": [
            ".docs-guidelines",
            ".sb-guidelines",
            "[data-section='guidelines']", 
            "h2:contains('Guidelines') + *",
            "h3:contains('Guidelines') + *"
        ],
        "examples": [
            ".docs-examples",
            ".sb-examples",
            "[data-section='examples']",
            "h2:contains('Examples') + *",
            "h3:contains('Examples') + *"
        ]
    }
    
    @staticmethod
    def extract_usage_guidelines(soup: BeautifulSoup) -> List[UsageGuideline]:
        """
        Extracts usage guidelines from component HTML.
        
        Args:
            soup: Parsed HTML document
            
        Returns:
            List of UsageGuideline objects
        """
        guidelines = []
        
        # Try to find guidelines section
        guidelines_content = ContentParser._find_section_content(soup, "guidelines")
        
        if guidelines_content:
            # Parse different guideline formats
            guidelines.extend(ContentParser._parse_guideline_lists(guidelines_content))
            guidelines.extend(ContentParser._parse_guideline_cards(guidelines_content))
            guidelines.extend(ContentParser._parse_guideline_paragraphs(guidelines_content))
            
        # Also look for do/don't patterns throughout the document
        guidelines.extend(ContentParser._extract_do_dont_guidelines(soup))
        
        return guidelines
        
    @staticmethod
    def _find_section_content(soup: BeautifulSoup, section: str) -> Optional[BeautifulSoup]:
        """Find content for a specific documentation section."""
        selectors = ContentParser.DOCS_SELECTORS.get(section, [])
        
        for selector in selectors:
            try:
                if ":contains(" in selector:
                    # Handle pseudo-selectors manually
                    selector_parts = selector.split(":contains(")
                    base_selector = selector_parts[0]
                    contains_text = selector_parts[1].split(")")[0].strip("'\"")
                    
                    # Find headers containing the text
                    headers = soup.find_all(base_selector.strip())
                    for header in headers:
                        if contains_text.lower() in header.get_text().lower():
                            # Get the next sibling or parent's next content
                            next_element = header.find_next_sibling()
                            if next_element:
                                return BeautifulSoup(str(next_element), 'html.parser')
                else:
                    elements = soup.select(selector)
                    if elements:
                        return BeautifulSoup(str(elements[0]), 'html.parser')
            except Exception as e:
                logger.warning(f"Error processing selector '{selector}': {e}")
                continue
                
        return None
        
    @staticmethod
    def _parse_guideline_lists(content: BeautifulSoup) -> List[UsageGuideline]:
        """Parse guidelines from list elements."""
        guidelines = []
        
        # Look for unordered lists
        lists = content.find_all(['ul', 'ol'])
        for list_elem in lists:
            items = list_elem.find_all('li')
            for item in items:
                text = ContentParser._clean_text(item.get_text())
                if text:
                    guideline_type = ContentParser._classify_guideline_type(text)
                    guidelines.append(UsageGuideline(
                        title=ContentParser._extract_guideline_title(text),
                        description=text,
                        type=guideline_type,
                        priority="normal"
                    ))
                    
        return guidelines
        
    @staticmethod
    def _parse_guideline_cards(content: BeautifulSoup) -> List[UsageGuideline]:
        """Parse guidelines from card-like elements."""
        guidelines = []
        
        # Look for common card selectors
        card_selectors = [
            ".guideline-card",
            ".docs-card",
            ".sb-card",
            "[data-type='guideline']"
        ]
        
        for selector in card_selectors:
            cards = content.select(selector)
            for card in cards:
                title_elem = card.find(['h3', 'h4', 'h5', '.card-title', '.guideline-title'])
                desc_elem = card.find(['p', '.card-description', '.guideline-description'])
                
                if title_elem or desc_elem:
                    title = ContentParser._clean_text(title_elem.get_text()) if title_elem else ""
                    description = ContentParser._clean_text(desc_elem.get_text()) if desc_elem else ""
                    
                    if title or description:
                        guideline_type = ContentParser._classify_guideline_type(title + " " + description)
                        guidelines.append(UsageGuideline(
                            title=title or ContentParser._extract_guideline_title(description),
                            description=description or title,
                            type=guideline_type,
                            priority="normal"
                        ))
                        
        return guidelines
        
    @staticmethod
    def _parse_guideline_paragraphs(content: BeautifulSoup) -> List[UsageGuideline]:
        """Parse guidelines from paragraph elements."""
        guidelines = []
        
        paragraphs = content.find_all('p')
        for p in paragraphs:
            text = ContentParser._clean_text(p.get_text())
            if text and len(text) > 20:  # Filter out very short paragraphs
                guideline_type = ContentParser._classify_guideline_type(text)
                guidelines.append(UsageGuideline(
                    title=ContentParser._extract_guideline_title(text),
                    description=text,
                    type=guideline_type,
                    priority="normal"
                ))
                
        return guidelines
        
    @staticmethod
    def _extract_do_dont_guidelines(soup: BeautifulSoup) -> List[UsageGuideline]:
        """Extract do/don't guidelines from the entire document."""
        guidelines = []
        
        # Look for elements with do/don't indicators
        do_dont_indicators = [
            r'\b(do|don\'t|avoid|never|always|should|shouldn\'t|must|must not)\b',
            r'✓|✗|❌|✅|👍|👎'
        ]
        
        all_elements = soup.find_all(text=True)
        for text_node in all_elements:
            text = ContentParser._clean_text(str(text_node))
            if not text or len(text) < 10:
                continue
                
            for pattern in do_dont_indicators:
                if re.search(pattern, text, re.IGNORECASE):
                    guideline_type = ContentParser._classify_guideline_type(text)
                    if guideline_type in ["do", "dont"]:
                        guidelines.append(UsageGuideline(
                            title=ContentParser._extract_guideline_title(text),
                            description=text,
                            type=guideline_type,
                            priority="high"
                        ))
                    break
                    
        return guidelines
        
    @staticmethod
    def _classify_guideline_type(text: str) -> str:
        """Classify the type of guideline based on text content."""
        text_lower = text.lower()
        
        # Check for explicit do/don't patterns
        if any(word in text_lower for word in ["don't", "don't", "avoid", "never", "shouldn't", "must not"]):
            return "dont"
        elif any(word in text_lower for word in ["do", "should", "always", "must", "recommended"]):
            return "do"
        elif any(word in text_lower for word in ["best practice", "tip", "note"]):
            return "best_practice"
        else:
            return "guideline"
            
    @staticmethod
    def _extract_guideline_title(text: str, max_length: int = 60) -> str:
        """Extract a title from guideline text."""
        # Take first sentence or first part before punctuation
        sentences = re.split(r'[.!?]', text)
        title = sentences[0].strip()
        
        # Truncate if too long
        if len(title) > max_length:
            title = title[:max_length].rsplit(' ', 1)[0] + "..."
            
        return title
        
    @staticmethod
    def extract_code_examples(soup: BeautifulSoup) -> List[CodeExample]:
        """
        Extract code examples with syntax highlighting information.
        
        Args:
            soup: Parsed HTML document
            
        Returns:
            List of CodeExample objects
        """
        examples = []
        
        # Find code blocks
        for selector in ContentParser.CODE_BLOCK_SELECTORS:
            code_elements = soup.select(selector)
            for elem in code_elements:
                code_text = elem.get_text().strip()
                if not code_text or len(code_text) < 10:  # Skip very short code snippets
                    continue
                    
                # Determine language from class or context
                language = ContentParser._detect_code_language(elem)
                
                # Find associated title/description
                title, description = ContentParser._find_code_context(elem)
                
                examples.append(CodeExample(
                    title=title or f"Code Example {len(examples) + 1}",
                    code=code_text,
                    language=language,
                    description=description
                ))
                
        return examples
        
    @staticmethod
    def _detect_code_language(elem: Tag) -> str:
        """Detect programming language from code element."""
        # Check class names for language hints
        classes = elem.get('class', [])
        for cls in classes:
            if cls.startswith('language-'):
                return cls.replace('language-', '')
            elif cls in {'typescript', 'javascript', 'tsx', 'jsx', 'html', 'css'}:
                return cls
                
        # Check parent classes
        parent = elem.parent
        if parent:
            parent_classes = parent.get('class', [])
            for cls in parent_classes:
                if cls.startswith('language-'):
                    return cls.replace('language-', '')
                    
        # Analyze code content for language hints
        code_text = elem.get_text()
        if 'import' in code_text and ('React' in code_text or 'Component' in code_text):
            return 'typescript' if 'interface' in code_text or ': ' in code_text else 'javascript'
        elif '<' in code_text and '>' in code_text and 'function' in code_text:
            return 'tsx'
        elif '<' in code_text and '>' in code_text:
            return 'jsx'
            
        return 'typescript'  # Default for React Storybook
        
    @staticmethod
    def _find_code_context(elem: Tag) -> Tuple[Optional[str], Optional[str]]:
        """Find title and description for a code block."""
        title = None
        description = None
        
        # Look for preceding heading
        prev_elements = []
        current = elem
        for _ in range(5):  # Look at previous 5 elements
            current = current.find_previous_sibling()
            if current is None:
                break
            prev_elements.append(current)
            
        for prev_elem in prev_elements:
            if prev_elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                title = ContentParser._clean_text(prev_elem.get_text())
                break
            elif prev_elem.name == 'p' and not description:
                text = ContentParser._clean_text(prev_elem.get_text())
                if text and len(text) < 200:  # Reasonable description length
                    description = text
                    
        # Look for following description if none found
        if not description:
            next_elem = elem.find_next_sibling()
            if next_elem and next_elem.name == 'p':
                text = ContentParser._clean_text(next_elem.get_text())
                if text and len(text) < 200:
                    description = text
                    
        return title, description
        
    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ""
            
        # Remove extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common code artifacts
        cleaned = re.sub(r'\bCopy\b', '', cleaned, flags=re.IGNORECASE)  # Case-insensitive, standalone word "Copy"
        cleaned = re.sub(r'^\d+\s*$', '', cleaned)  # Line numbers
        
        return cleaned.strip()
        
    @staticmethod
    def extract_iframe_content(soup: BeautifulSoup) -> Dict[str, str]:
        """
        Extract content from Storybook iframe elements.
        
        Args:
            soup: Parsed HTML document
            
        Returns:
            Dictionary of extracted iframe content
        """
        iframe_content = {}
        
        # Look for Storybook root element
        storybook_root = soup.find(id="storybook-root")
        if storybook_root:
            iframe_content["component_html"] = str(storybook_root)
            iframe_content["component_text"] = ContentParser._clean_text(storybook_root.get_text())
            
        # Look for canvas content
        canvas_elements = soup.select(".sb-show-main, .sb-main-centered, .sb-main-fullscreen")
        if canvas_elements:
            iframe_content["canvas_html"] = str(canvas_elements[0])
            iframe_content["canvas_text"] = ContentParser._clean_text(canvas_elements[0].get_text())
            
        return iframe_content
    
    @staticmethod
    def parse_html_to_text(html_content: str, main_content_selectors: Optional[List[str]] = None) -> str:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Pre-emptive removal of common non-content tags from the entire soup
        # Added svg and path as they are common in UI libraries and rarely contain useful text for KG.
        for element in soup(["script", "style", "header", "footer", "nav", "aside", "form", "button", "iframe", "noscript", "svg", "path"]):
            element.decompose()

        # Attempt to use main_content_selectors if provided
        if main_content_selectors:
            selected_texts = []
            for selector in main_content_selectors:
                elements = soup.select(selector)
                for el in elements:
                    # Clean the selected element further in case it contains nested unwanted tags
                    # This ensures that even if a main selector grabs a large chunk, unwanted sub-elements are removed.
                    for sub_element in el(["script", "style", "header", "footer", "nav", "aside", "form", "button", "iframe", "noscript", "svg", "path"]):
                        sub_element.decompose()
                    selected_texts.append(el.get_text(separator=' ', strip=True))
            
            if selected_texts and any(text.strip() for text in selected_texts):
                full_text = ' '.join(filter(None, selected_texts))
                return ' '.join(full_text.split()) # Normalize whitespace

        # Fallback: if no selectors provided, or they yield no text, process the body or the whole document.
        # The soup has already been cleaned by the initial decompose loop.
        target_element = soup.find('body') or soup 

        text_content = target_element.get_text(separator=' ', strip=True)
        
        # Normalize whitespace (e.g., multiple spaces to one, remove leading/trailing for the whole string)
        normalized_text = ' '.join(text_content.split())
        
        return normalized_text
