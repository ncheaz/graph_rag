"""
Relationship analyzer for mapping component dependencies.

Uses AST-based analysis and DOM structure analysis to identify component 
relationships and build dependency graphs.
"""

import re
import ast
from typing import List, Dict, Set, Optional, Tuple
from bs4 import BeautifulSoup, Tag
from .data_models import ComponentDependency


class RelationshipAnalyzer:
    """Analyzes component relationships and dependencies."""
    
    # Common import patterns in React/TypeScript
    IMPORT_PATTERNS = [
        r'import\s+(?:{[^}]+}|\*\s+as\s+\w+|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',
        r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
    ]
    
    # Component reference patterns
    COMPONENT_REF_PATTERNS = [
        r'<(\w+)(?:\s|>|/>)',  # JSX component usage
        r'(\w+)\.(\w+)',       # Namespace usage
        r'extends\s+(\w+)',     # Class inheritance
        r'implements\s+(\w+)'   # Interface implementation
    ]
    
    @staticmethod
    def find_component_dependencies(component_name: str, 
                                  code_content: str,
                                  html_content: str) -> List[ComponentDependency]:
        """
        Identifies component dependencies through AST and DOM analysis.
        
        Args:
            component_name: Name of the source component
            code_content: Code examples from the component
            html_content: HTML content of the component page
            
        Returns:
            List of ComponentDependency objects
        """
        dependencies = []
        
        # Extract dependencies from code content
        if code_content:
            dependencies.extend(RelationshipAnalyzer._analyze_code_dependencies(
                component_name, code_content
            ))
            
        # Extract dependencies from HTML structure
        if html_content:
            soup = BeautifulSoup(html_content, 'html.parser')
            dependencies.extend(RelationshipAnalyzer._analyze_dom_dependencies(
                component_name, soup
            ))
            
        # Remove duplicates
        seen = set()
        unique_dependencies = []
        for dep in dependencies:
            key = (dep.source, dep.target, dep.relationship_type)
            if key not in seen:
                seen.add(key)
                unique_dependencies.append(dep)
                
        return unique_dependencies
        
    @staticmethod
    def _analyze_code_dependencies(component_name: str, code_content: str) -> List[ComponentDependency]:
        """Analyze dependencies from code examples."""
        dependencies = []
        
        # Extract import statements
        imports = RelationshipAnalyzer._extract_imports(code_content)
        for import_path, imported_items in imports.items():
            for item in imported_items:
                dependencies.append(ComponentDependency(
                    source=component_name,
                    target=item,
                    relationship_type="imports",
                    description=f"Imports {item} from {import_path}"
                ))
                
        # Extract component references
        component_refs = RelationshipAnalyzer._extract_component_references(code_content)
        for ref_component in component_refs:
            if ref_component != component_name:  # Don't self-reference
                dependencies.append(ComponentDependency(
                    source=component_name,
                    target=ref_component,
                    relationship_type="uses",
                    description=f"Uses {ref_component} component"
                ))
                
        # Extract inheritance relationships
        inheritance = RelationshipAnalyzer._extract_inheritance(code_content)
        for parent_class in inheritance:
            dependencies.append(ComponentDependency(
                source=component_name,
                target=parent_class,
                relationship_type="extends",
                description=f"Extends {parent_class}"
            ))
            
        return dependencies
        
    @staticmethod
    def _extract_imports(code_content: str) -> Dict[str, List[str]]:
        """Extract import statements and their imported items."""
        imports = {}
        
        for pattern in RelationshipAnalyzer.IMPORT_PATTERNS:
            matches = re.finditer(pattern, code_content, re.MULTILINE)
            for match in matches:
                import_path = match.group(1)
                
                # Find the full import statement
                import_statement = RelationshipAnalyzer._find_import_statement(
                    code_content, match.start()
                )
                
                if import_statement:
                    imported_items = RelationshipAnalyzer._parse_imported_items(import_statement)
                    if imported_items:
                        imports[import_path] = imported_items
                        
        return imports
        
    @staticmethod
    def _find_import_statement(code_content: str, start_pos: int) -> Optional[str]:
        """Find the complete import statement starting from a position."""
        lines = code_content.split('\n')
        char_count = 0
        
        for line in lines:
            if char_count <= start_pos <= char_count + len(line):
                # Found the line containing the import
                stripped = line.strip()
                if stripped.startswith('import'):
                    return stripped
            char_count += len(line) + 1  # +1 for newline
            
        return None
        
    @staticmethod
    def _parse_imported_items(import_statement: str) -> List[str]:
        """Parse imported items from an import statement."""
        items = []
        
        # Handle different import formats
        if 'import {' in import_statement:
            # Named imports: import { Button, Icon } from 'library'
            start = import_statement.find('{') + 1
            end = import_statement.find('}')
            if start > 0 and end > start:
                imports_text = import_statement[start:end]
                items = [item.strip() for item in imports_text.split(',')]
        elif 'import * as' in import_statement:
            # Namespace import: import * as Utils from 'library'
            match = re.search(r'import\s+\*\s+as\s+(\w+)', import_statement)
            if match:
                items = [match.group(1)]
        elif 'import' in import_statement and 'from' in import_statement:
            # Default import: import Button from 'library'
            match = re.search(r'import\s+(\w+)\s+from', import_statement)
            if match:
                items = [match.group(1)]
                
        return [item.strip() for item in items if item.strip()]
        
    @staticmethod
    def _extract_component_references(code_content: str) -> Set[str]:
        """Extract component references from JSX/TSX code."""
        components = set()
        
        # Find JSX component usage
        jsx_pattern = r'<(\w+)(?:\s|>|/>)'
        matches = re.finditer(jsx_pattern, code_content)
        for match in matches:
            component_name = match.group(1)
            # Filter out HTML elements (lowercase) and common non-components
            if (component_name[0].isupper() and 
                component_name not in ['React', 'Fragment', 'Suspense']):
                components.add(component_name)
                
        return components
        
    @staticmethod
    def _extract_inheritance(code_content: str) -> Set[str]:
        """Extract class inheritance relationships."""
        inheritance = set()
        
        # Find extends and implements
        extends_pattern = r'(?:class|interface)\s+\w+\s+extends\s+(\w+)'
        implements_pattern = r'class\s+\w+\s+implements\s+(\w+)'
        
        for pattern in [extends_pattern, implements_pattern]:
            matches = re.finditer(pattern, code_content)
            for match in matches:
                inheritance.add(match.group(1))
                
        return inheritance
        
    @staticmethod
    def _analyze_dom_dependencies(component_name: str, soup: BeautifulSoup) -> List[ComponentDependency]:
        """Analyze dependencies from DOM structure."""
        dependencies = []
        
        # Look for referenced components in documentation
        doc_references = RelationshipAnalyzer._find_documentation_references(soup)
        for ref_component in doc_references:
            if ref_component != component_name:
                dependencies.append(ComponentDependency(
                    source=component_name,
                    target=ref_component,
                    relationship_type="references",
                    description=f"Referenced in documentation"
                ))
                
        # Look for related components in navigation or links
        nav_references = RelationshipAnalyzer._find_navigation_references(soup)
        for ref_component in nav_references:
            if ref_component != component_name:
                dependencies.append(ComponentDependency(
                    source=component_name,
                    target=ref_component,
                    relationship_type="related",
                    description=f"Related component in navigation"
                ))
                
        return dependencies
        
    @staticmethod
    def _find_documentation_references(soup: BeautifulSoup) -> Set[str]:
        """Find component references in documentation text."""
        references = set()
        
        # Look for component names in text (PascalCase words)
        text_content = soup.get_text()
        pascal_case_pattern = r'\b([A-Z][a-zA-Z]*(?:[A-Z][a-zA-Z]*)*)\b'
        matches = re.finditer(pascal_case_pattern, text_content)
        
        for match in matches:
            word = match.group(1)
            # Filter potential component names
            if (len(word) > 2 and 
                word not in ['API', 'HTML', 'CSS', 'DOM', 'URL', 'JSON', 'XML'] and
                not word.endswith('s')):  # Avoid plurals
                references.add(word)
                
        return references
        
    @staticmethod
    def _find_navigation_references(soup: BeautifulSoup) -> Set[str]:
        """Find component references in navigation elements."""
        references = set()
        
        # Look for navigation links
        nav_selectors = [
            'nav a',
            '.navigation a',
            '.sidebar a',
            '[data-testid*="nav"] a',
            '.storybook-nav a'
        ]
        
        for selector in nav_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href', '')
                text = link.get_text().strip()
                
                # Extract component name from href or text
                component_name = RelationshipAnalyzer._extract_component_name_from_link(href, text)
                if component_name:
                    references.add(component_name)
                    
        return references
        
    @staticmethod
    def _extract_component_name_from_link(href: str, text: str) -> Optional[str]:
        """Extract component name from a navigation link."""
        # Try to extract from href path
        if href:
            # Look for patterns like /component-name or ?component=ComponentName
            path_match = re.search(r'/([a-zA-Z-]+)(?:--|\?|$)', href)
            if path_match:
                # Convert kebab-case to PascalCase
                kebab_name = path_match.group(1)
                pascal_name = ''.join(word.capitalize() for word in kebab_name.split('-'))
                return pascal_name
                
            # Look for query parameters
            param_match = re.search(r'[?&](?:component|story)=([^&]+)', href)
            if param_match:
                return param_match.group(1)
                
        # Try to extract from link text
        if text:
            # Clean up text and check if it looks like a component name
            clean_text = re.sub(r'[^a-zA-Z]', '', text)
            if clean_text and clean_text[0].isupper() and len(clean_text) > 2:
                return clean_text
                
        return None
        
    @staticmethod
    def analyze_component_relationships(components_data: List[Dict]) -> Dict[str, List[ComponentDependency]]:
        """
        Analyze relationships between multiple components.
        
        Args:
            components_data: List of component data dictionaries
            
        Returns:
            Dictionary mapping component names to their dependencies
        """
        all_dependencies = {}
        component_names = {comp.get('name', '') for comp in components_data}
        
        for comp_data in components_data:
            comp_name = comp_data.get('name', '')
            if not comp_name:
                continue
                
            # Get code content from examples
            code_content = ""
            examples = comp_data.get('examples', [])
            for example in examples:
                if isinstance(example, dict):
                    code_content += example.get('code', '') + "\n"
                    
            # Get HTML content
            html_content = comp_data.get('html', '')
            
            # Find dependencies
            dependencies = RelationshipAnalyzer.find_component_dependencies(
                comp_name, code_content, html_content
            )
            
            # Filter dependencies to only include known components
            filtered_dependencies = []
            for dep in dependencies:
                if dep.target in component_names:
                    filtered_dependencies.append(dep)
                    
            all_dependencies[comp_name] = filtered_dependencies
            
        return all_dependencies
