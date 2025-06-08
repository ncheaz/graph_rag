"""
Main extraction orchestrator for processing crawled component data.

Coordinates the extraction pipeline: metadata -> content -> relationships -> knowledge graph.
Processes JSON files from the crawler and outputs structured component data.
"""

import json
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .metadata_extractor import MetadataExtractor
from .content_parser import ContentParser
from .relationship_analyzer import RelationshipAnalyzer
from .kg_extractor import KGExtractor
from .data_models import ExtractedComponent, ComponentProperty, KGResult


logger = logging.getLogger(__name__)


class ExtractionOrchestrator:
    """Orchestrates the complete extraction pipeline."""
    
    def __init__(self,
                 crawler_output_dir: str = "process/crawler",
                 output_dir: str = "process/extraction"):
        """
        Initialize the extraction orchestrator.
        
        Args:
            crawler_output_dir: Directory containing crawler JSON files
            output_dir: Directory for extraction outputs
        """
        self.crawler_output_dir = Path(crawler_output_dir)
        self.output_dir = Path(output_dir)
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize extractors
        self.metadata_extractor = MetadataExtractor()
        self.content_parser = ContentParser()
        self.relationship_analyzer = RelationshipAnalyzer()
        
        try:
            self.kg_extractor = KGExtractor()
            logger.info("KG extractor initialized")
        except Exception as e:
            logger.error(f"Failed to initialize KG extractor: {e}")
            raise
            
    def process_all_components(self) -> Dict[str, Any]:
        """
        Process all JSON files from the crawler output directory.
        
        Returns:
            Summary of extraction results
        """
        logger.info(f"Starting extraction from {self.crawler_output_dir}")
        
        # Find all JSON files
        json_files = list(self.crawler_output_dir.glob("*.json"))
        logger.info(f"Found {len(json_files)} JSON files to process")
        
        if not json_files:
            logger.warning("No JSON files found in crawler output directory")
            return {"error": "No JSON files found"}
            
        # Process each file
        extracted_components = []
        kg_results = []
        processing_errors = []
        
        for json_file in json_files:
            try:
                logger.info(f"Processing {json_file.name}")
                
                # Load crawler data
                with open(json_file, 'r', encoding='utf-8') as f:
                    crawler_data = json.load(f)
                    
                # Extract component data
                component_data = self.extract_component(crawler_data)
                extracted_components.append(component_data)
                
                # Save individual component data
                self._save_component_data(component_data)
                
                # Extract knowledge graph if enabled
                if self.enable_kg_extraction:
                    kg_result = self.kg_extractor.extract_knowledge_graph(
                        component_data, 
                        crawler_data.get('html', '')
                    )
                    kg_results.append(kg_result)
                    self._save_kg_result(kg_result)
                    
            except Exception as e:
                error_msg = f"Failed to process {json_file.name}: {e}"
                logger.error(error_msg)
                processing_errors.append(error_msg)
                
        # Analyze relationships between all components
        if extracted_components:
            self._analyze_cross_component_relationships(extracted_components)
            
        # Combine and save KG results
        if kg_results:
            combined_kg = KGExtractor.combine_kg_results(kg_results)
            self._save_combined_kg_result(combined_kg)
            
        # Generate summary
        summary = {
            "extraction_timestamp": datetime.now().isoformat(),
            "total_files_processed": len(json_files),
            "successful_extractions": len(extracted_components),
            "kg_extractions": len(kg_results),
            "processing_errors": processing_errors,
            "output_directory": str(self.output_dir),
            "components": [comp.metadata.name for comp in extracted_components]
        }
        
        # Save summary
        summary_file = self.output_dir / "extraction_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, default=str)
            
        logger.info(f"Extraction complete. Summary saved to {summary_file}")
        return summary
        
    def extract_component(self, crawler_data: Dict[str, Any]) -> ExtractedComponent:
        """
        Extract complete component data from crawler JSON.
        
        Args:
            crawler_data: JSON data from crawler
            
        Returns:
            ExtractedComponent with all extracted information
        """
        # Extract basic metadata
        metadata = MetadataExtractor.extract_component_metadata(
            html_content=crawler_data.get('html', ''),
            name=crawler_data.get('name', 'Unknown'),
            url=crawler_data.get('url', '')
        )
        
        # Parse HTML content
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(crawler_data.get('html', ''), 'html.parser')
        
        # Extract properties from args table
        properties_data = MetadataExtractor.extract_properties_table(soup)
        properties = [
            ComponentProperty(
                name=prop['name'],
                description=prop['description'],
                type=prop.get('control', 'unknown'),
                default_value=prop.get('default'),
                required=prop.get('required', False)
            )
            for prop in properties_data
        ]
        
        # Extract usage guidelines
        guidelines = ContentParser.extract_usage_guidelines(soup)
        
        # Extract code examples
        examples = ContentParser.extract_code_examples(soup)
        
        # Find dependencies (will be enhanced with cross-component analysis)
        dependencies = RelationshipAnalyzer.find_component_dependencies(
            component_name=metadata.name,
            code_content='\n'.join(ex.code for ex in examples),
            html_content=crawler_data.get('html', '')
        )
        
        return ExtractedComponent(
            metadata=metadata,
            properties=properties,
            guidelines=guidelines,
            examples=examples,
            dependencies=dependencies,
            raw_content=soup.get_text()[:1000],  # First 1000 chars as summary
            extraction_timestamp=datetime.now()
        )
        
    def _save_component_data(self, component_data: ExtractedComponent) -> None:
        """Save individual component data to JSON file."""
        filename = f"{component_data.metadata.name}_extracted.json"
        filepath = self.output_dir / filename
        
        # Convert to dict for JSON serialization
        data_dict = {
            "metadata": {
                "name": component_data.metadata.name,
                "title": component_data.metadata.title,
                "url": component_data.metadata.url,
                "description": component_data.metadata.description,
                "category": component_data.metadata.category,
                "tags": component_data.metadata.tags,
                "last_modified": component_data.metadata.last_modified.isoformat()
            },
            "properties": [
                {
                    "name": prop.name,
                    "description": prop.description,
                    "type": prop.type,
                    "default_value": prop.default_value,
                    "required": prop.required,
                    "options": prop.options
                }
                for prop in component_data.properties
            ],
            "guidelines": [
                {
                    "title": guideline.title,
                    "description": guideline.description,
                    "type": guideline.type,
                    "priority": guideline.priority
                }
                for guideline in component_data.guidelines
            ],
            "examples": [
                {
                    "title": example.title,
                    "code": example.code,
                    "language": example.language,
                    "description": example.description
                }
                for example in component_data.examples
            ],
            "dependencies": [
                {
                    "source": dep.source,
                    "target": dep.target,
                    "relationship_type": dep.relationship_type,
                    "description": dep.description
                }
                for dep in component_data.dependencies
            ],
            "extraction_timestamp": component_data.extraction_timestamp.isoformat()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, indent=2, ensure_ascii=False)
            
        logger.debug(f"Saved component data to {filepath}")
        
    def _save_kg_result(self, kg_result: KGResult) -> None:
        """Save KG extraction result to JSON file."""
        filename = f"{kg_result.source_component}_kg.json"
        filepath = self.output_dir / filename
        
        # Convert to dict for JSON serialization
        data_dict = {
            "entities": [
                {
                    "id": entity.id,
                    "type": entity.type,
                    "properties": entity.properties
                }
                for entity in kg_result.entities
            ],
            "relations": [
                {
                    "source_id": relation.source_id,
                    "target_id": relation.target_id,
                    "relation_type": relation.relation_type,
                    "properties": relation.properties
                }
                for relation in kg_result.relations
            ],
            "source_component": kg_result.source_component,
            "extraction_metadata": kg_result.extraction_metadata
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, indent=2, ensure_ascii=False)
            
        logger.debug(f"Saved KG result to {filepath}")
        
    def _save_combined_kg_result(self, combined_kg: KGResult) -> None:
        """Save combined KG result."""
        filepath = self.output_dir / "combined_kg.json"
        
        data_dict = {
            "entities": [
                {
                    "id": entity.id,
                    "type": entity.type,
                    "properties": entity.properties
                }
                for entity in combined_kg.entities
            ],
            "relations": [
                {
                    "source_id": relation.source_id,
                    "target_id": relation.target_id,
                    "relation_type": relation.relation_type,
                    "properties": relation.properties
                }
                for relation in combined_kg.relations
            ],
            "extraction_metadata": combined_kg.extraction_metadata
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Saved combined KG result to {filepath}")
        
    def _analyze_cross_component_relationships(self, components: List[ExtractedComponent]) -> None:
        """Analyze relationships between all components."""
        logger.info("Analyzing cross-component relationships")
        
        # Convert to format expected by relationship analyzer
        components_data = []
        for comp in components:
            comp_dict = {
                'name': comp.metadata.name,
                'html': comp.raw_content,
                'examples': [
                    {'code': ex.code} for ex in comp.examples
                ]
            }
            components_data.append(comp_dict)
            
        # Analyze relationships
        all_relationships = RelationshipAnalyzer.analyze_component_relationships(components_data)
        
        # Save relationship analysis
        relationships_file = self.output_dir / "component_relationships.json"
        with open(relationships_file, 'w', encoding='utf-8') as f:
            # Convert to serializable format
            serializable_relationships = {}
            for comp_name, deps in all_relationships.items():
                serializable_relationships[comp_name] = [
                    {
                        "source": dep.source,
                        "target": dep.target,
                        "relationship_type": dep.relationship_type,
                        "description": dep.description
                    }
                    for dep in deps
                ]
            json.dump(serializable_relationships, f, indent=2)
            
        logger.info(f"Saved relationship analysis to {relationships_file}")
        
    def process_single_component(self, json_file_path: str) -> ExtractedComponent:
        """
        Process a single component JSON file.
        
        Args:
            json_file_path: Path to the JSON file
            
        Returns:
            ExtractedComponent object
        """
        with open(json_file_path, 'r', encoding='utf-8') as f:
            crawler_data = json.load(f)
            
        return self.extract_component(crawler_data)


# Main extraction function for CLI usage
def main():
    """Main function for running extraction from command line."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract structured data from crawled components")
    parser.add_argument("--input-dir", default="process/crawler", 
                       help="Directory containing crawler JSON files")
    parser.add_argument("--output-dir", default="process/extraction",
                       help="Directory for extraction outputs")
    parser.add_argument("--no-kg", action="store_true",
                       help="Disable knowledge graph extraction")
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run extraction
    orchestrator = ExtractionOrchestrator(
        crawler_output_dir=args.input_dir,
        output_dir=args.output_dir,
        enable_kg_extraction=not args.no_kg
    )
    
    summary = orchestrator.process_all_components()
    print(f"Extraction complete. Processed {summary['successful_extractions']} components.")
    
    if summary.get('processing_errors'):
        print(f"Errors encountered: {len(summary['processing_errors'])}")
        for error in summary['processing_errors']:
            print(f"  - {error}")


if __name__ == "__main__":
    main()
