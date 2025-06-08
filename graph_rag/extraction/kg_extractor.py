"""
Knowledge Graph Extractor using LlamaIndex PropertyGraphIndex.
Final working implementation.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
from llama_index.core import Document, PropertyGraphIndex, Settings
from llama_index.core.indices.property_graph import SchemaLLMPathExtractor
from llama_index.core.graph_stores import SimpleGraphStore
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from .data_models import KGResult, KGEntity, KGRelation, ExtractedComponent
from llama_index.llms.deepseek import DeepSeek

logger = logging.getLogger(__name__)

class KGExtractor:
    """Extracts knowledge graphs from component documentation."""
    
    def __init__(self,
                 llm_model: Optional[str] = None,
                 embedding_model: Optional[str] = None,
                 temperature: float = 0.1):
        # Validate OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is required")
            
        # Get required base URL and model
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
        model_name = os.getenv("OPENAI_MODEL", "deepseek-chat")
        
        # General LLM model name for logging
        llm_model_display_name = llm_model or model_name
        embedding_model_name = embedding_model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        
        # Specific model name for the OpenAI client
        actual_model_for_client = model_name
        
        # Initialize OpenAI client with Deepseek configuration
        self.llm = DeepSeek(
            model="deepseek-chat",
            temperature=temperature,
            api_base="https://api.deepseek.com",
            api_key=os.getenv("OPENAI_API_KEY")
        )
        Settings.llm = self.llm

        # Configure embeddings - use a simple embedder since we're focused on KG extraction
        from llama_index.core.embeddings import BaseEmbedding
        class DummyEmbedding(BaseEmbedding):
            def _get_query_embedding(self, query: str) -> List[float]:
                return [0.0] * 384
                
            def _get_text_embedding(self, text: str) -> List[float]:
                return [0.0] * 384
                
            async def _aget_text_embedding(self, text: str) -> List[float]:
                return [0.0] * 384
                
            async def _aget_query_embedding(self, query: str) -> List[float]:
                return [0.0] * 384
                
        Settings.embed_model = DummyEmbedding(embed_batch_size=1)
        
        logger.info(f"Initialized KGExtractor with LLM configuration for: {actual_model_for_client} (display name: {llm_model_display_name}, base_url: {base_url})")

    def _prepare_document_text(self,
                            component_data: ExtractedComponent,
                            html_content: str) -> str:
        """Prepare document text from component data and HTML content.
        
        Args:
            component_data: Extracted component metadata and properties
            html_content: Raw HTML content of the component documentation
            
        Returns:
            Combined document text for knowledge graph extraction
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try to extract content from storybook-root div first
        storybook_root = soup.find('div', id='storybook-root')
        html_text = ""
        
        if storybook_root:
            # Found storybook content - extract text from this div
            html_text = storybook_root.get_text(separator='\n', strip=True)
            logger.debug(f"Extracted content from #storybook-root: {html_text[:200]}...")
        else:
            # Check if this is an error page
            error_div = soup.find('div', class_='sb-nopreview')
            if error_div and "Sorry, but you" in error_div.get_text():
                logger.warning("Found Storybook error page - using minimal content")
                html_text = "Component documentation not available"
            else:
                # Fallback to full text extraction
                html_text = soup.get_text(separator='\n', strip=True)
                logger.debug(f"Using full HTML content as fallback: {html_text[:200]}...")
        
        # Verify we have clean text (no HTML tags)
        if "<" in html_text or ">" in html_text:
            logger.warning("HTML tags detected in extracted text - cleaning")
            html_text = BeautifulSoup(html_text, 'html.parser').get_text()
        
        # Prepare structured component metadata with enhanced LLM prompt
        description = component_data.metadata.description or "Component documentation"
        if description and "Sorry, but you" in description:
            description = "Component documentation"
            
        # Prepare properties section only if we have valid properties
        properties_text = ""
        if component_data.properties:
            properties_text = "\nProperties:\n"
            for prop in component_data.properties:
                if "short descriptionsummary" not in prop.description.lower():
                    properties_text += f"""
- Property: {prop.name}
Type: {prop.type}
Description: {prop.description}
Default: {prop.default_value or 'None'}
Required: {'Yes' if prop.required else 'No'}
"""
                    # Explicitly relate property to component
                    properties_text += f"Relation: ({component_data.metadata.name}, has_property, {prop.name})\n"
        
        component_text = f"""
Extract knowledge triplets from this structured component documentation.
Follow the format: (subject, predicate, object)

Examples of valid triplets:
- (ComponentName, has_property, PropertyName)
- (PropertyName, has_type, TypeName)
- (PropertyName, has_default_value, DefaultValue)
- (ComponentName, has_value, NumericalValue)
- (PropertyName, has_value, NumericalValue)

Component Metadata:
- Name: {component_data.metadata.name}
- Description: {description}
- Category: {component_data.metadata.category or 'Uncategorized'}
{properties_text}
"""

        # Add numerical data points if present in HTML with explicit relations
        soup = BeautifulSoup(html_content, 'html.parser')
        numerical_data = []
        for element in soup.find_all(string=True):
            text = element.strip()
            if text.replace('.','',1).isdigit():  # Check if numeric
                numerical_data.append(text)
        
        if numerical_data:
            component_text += "\nNumerical Data Points:\n"
            for value in numerical_data:
                component_text += f"- Value: {value}\n"
                # Explicitly relate numerical values to component
                component_text += f"Possible relations:\n"
                component_text += f"({component_data.metadata.name}, has_value, {value})\n"
                if component_data.properties:
                    for prop in component_data.properties:
                        component_text += f"({prop.name}, has_value, {value})\n"
        
        # Combine both sources with clear separation
        return f"""{component_text}

Documentation Content:
{html_text}

Extract knowledge triplets from both the structured metadata and documentation content.
Focus on relationships between:
- Components and their properties
- Properties and their types/values
- Components and numerical values
- Properties and numerical values

For numerical values, create explicit relationships to either the component or its properties.
"""

    def extract_knowledge_graph(self,
                             component_data: ExtractedComponent,
                             html_content: str) -> KGResult:
        """Extract knowledge graph from component data using PropertyGraphIndex."""
        try:
            # Validate HTML content
            soup = BeautifulSoup(html_content, 'html.parser')
            storybook_root = soup.find('div', id='storybook-root')
            error_div = soup.find('div', class_='sb-nopreview')
            
            # Only treat as error page if we have explicit error message AND no valid content
            if (error_div and "Sorry, but you" in error_div.get_text() and
                not storybook_root and len(html_content) < 500):
                logger.warning("Possible error page detected - but attempting extraction anyway")
            
            # Check for minimum viable content
            if len(html_content) < 100:
                logger.error(f"HTML content too short ({len(html_content)} chars) - likely invalid")
                logger.debug(f"Raw content preview: {html_content[:200]}...")
                return self._manual_extraction(component_data)
            
            # Prepare document content
            document_text = self._prepare_document_text(component_data, html_content)
            logger.debug(f"Document text preview: {document_text[:200]}...")
            
            # Test LLM connection with proper async context
            try:
                import asyncio
                import nest_asyncio
                nest_asyncio.apply()
                
                async def test_llm_connection():
                    try:
                        test_prompt = "Extract knowledge triplets from: 'Button component has property color with values red, blue, green'"
                        logger.debug(f"Sending test prompt to LLM: {test_prompt}")
                        response = await self.llm.acomplete(test_prompt)
                        logger.debug(f"Received test response: {response}")
                        
                        # Validate response contains expected triplet format
                        if not any(x in str(response) for x in ["(", ")", ","]):
                            raise ValueError("LLM response does not contain valid triplet format")
                        return response
                    except Exception as e:
                        logger.error(f"LLM request failed: {e}")
                        raise
                
                # Get or create event loop
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                test_response = loop.run_until_complete(test_llm_connection())
                logger.debug(f"LLM connection test response: {test_response}")
            except Exception as e:
                logger.error(f"LLM connection failed: {e}")
                return self._manual_extraction(component_data)
            
            # Initialize DynamicLLMPathExtractor with supported configuration
            logger.debug("Initializing DynamicLLMPathExtractor")
            from llama_index.core.indices.property_graph import DynamicLLMPathExtractor
            path_extractor = DynamicLLMPathExtractor(
                llm=Settings.llm,
                num_workers=4  # Only supported parameter
            )
            logger.debug(f"Initialized DynamicLLMPathExtractor with LLM: {Settings.llm}")
            
            # Create PropertyGraphIndex with retries and enhanced logging
            logger.debug("Creating PropertyGraphIndex with retries")
            graph_store = SimpleGraphStore()
            logger.debug(f"Document text length: {len(document_text)} chars")
            
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    # Create index with proper event loop management
                    import nest_asyncio
                    nest_asyncio.apply()
                    
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    # Log the document text being sent for extraction
                    logger.debug(f"Attempt {attempt+1}/{max_attempts} - Document text:\n{document_text[:500]}...")
                    
                    index = PropertyGraphIndex.from_documents(
                        documents=[Document(text=document_text)],
                        llm=self.llm,
                        graph_store=graph_store,
                        path_extractor=path_extractor,
                        max_triplets_per_chunk=30,  # Increased from 20
                        show_progress=True,
                        chunk_size=512  # Smaller chunks for better processing
                    )
                    
                    # Verify and log extracted paths with more tolerance
                    triples = graph_store.get(subj='')
                    if not triples:
                        if attempt < max_attempts - 1:
                            logger.warning(f"Empty graph store on attempt {attempt+1} - retrying")
                            continue
                        logger.warning("Graph store is empty after all attempts")
                        return self._manual_extraction(component_data)
                    
                    logger.info(f"Extracted {len(triples)} paths on attempt {attempt+1}:")
                    for i, (s, p, o) in enumerate(triples[:10]):  # Log more samples
                        logger.info(f"Path {i+1}: {s} -> {p} -> {o}")
                    
                    # More lenient validation of path structure
                    invalid_paths = [t for t in triples if not all(isinstance(x, str) and x.strip() for x in t)]
                    if invalid_paths:
                        logger.warning(f"Found {len(invalid_paths)} invalid paths (will attempt to filter)")
                        triples = [t for t in triples if all(isinstance(x, str) and x.strip() for x in t)]
                        if not triples:
                            logger.warning("All paths filtered as invalid")
                            return self._manual_extraction(component_data)
                    
                    break
                except Exception as e:
                    logger.error(f"KG extraction attempt {attempt+1} failed: {str(e)}")
                    if attempt == max_attempts - 1:
                        logger.error("All extraction attempts failed")
                        return self._manual_extraction(component_data)
            
            # Extract entities and relations from the graph store
            logger.debug("Extracting KG data from graph store")
            entities, relations = self._extract_kg_data(graph_store, component_data.metadata.name)
            
            # More tolerant check for results
            if len(entities) < 3:  # Require at least 3 entities to consider successful
                logger.warning(f"Insufficient entities extracted ({len(entities)}) - falling back to manual")
                return self._manual_extraction(component_data)
            
            logger.info(f"Successfully extracted {len(entities)} entities and {len(relations)} relations using DynamicLLMPathExtractor")
            
            return KGResult(
                entities=entities,
                relations=relations,
                source_component=component_data.metadata.name,
                extraction_metadata={
                    "document_length": len(document_text),
                    "extraction_model": str(Settings.llm),
                    "schema_version": "1.0",
                    "method": "DynamicLLMPathExtractor",
                    "attempts": max_attempts
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to extract KG: {e}")
            return KGResult(
                entities=[],
                relations=[],
                source_component=component_data.metadata.name,
                extraction_metadata={"error": str(e)}
            )

    def _manual_extraction(self,
                         component_data: ExtractedComponent) -> KGResult:
        """Enhanced manual knowledge extraction with numerical data handling."""
        logger.info("Attempting manual knowledge extraction")
        
        # Extract component as main entity
        component_entity = KGEntity(
            id=f"component_{component_data.metadata.name}",
            type="Component",
            properties={
                "name": component_data.metadata.name,
                "description": component_data.metadata.description,
                "category": component_data.metadata.category or "Uncategorized"
            }
        )
        entities = [component_entity]
        relations = []
        
        # Extract meaningful properties
        for prop in component_data.properties:
            # Skip generic placeholder properties
            if ("short descriptionsummary" in prop.description.lower() or
                "propertyName" in prop.name):
                continue
                
            prop_entity = KGEntity(
                id=f"property_{prop.name}",
                type="Property",
                properties={
                    "name": prop.name,
                    "type": prop.type,
                    "description": prop.description,
                    "default": prop.default_value or "None",
                    "required": str(prop.required),
                    "options": ",".join(prop.options) if prop.options else "None"
                }
            )
            entities.append(prop_entity)
            relations.append(KGRelation(
                source_id=component_entity.id,
                target_id=prop_entity.id,
                relation_type="has_property",
                properties={}
            ))

            # Create value entities for numerical options
            if prop.options and all(opt.replace('.','',1).isdigit() for opt in prop.options):
                for value in prop.options:
                    value_entity = KGEntity(
                        id=f"value_{prop.name}_{value}",
                        type="Value",
                        properties={
                            "value": value,
                            "unit": "unknown",
                            "property": prop.name
                        }
                    )
                    entities.append(value_entity)
                    relations.append(KGRelation(
                        source_id=prop_entity.id,
                        target_id=value_entity.id,
                        relation_type="has_value",
                        properties={}
                    ))

        # Extract numerical data points from HTML content
        soup = BeautifulSoup(component_data.raw_content, 'html.parser')
        numerical_values = set()
        for element in soup.find_all(string=True):
            text = element.strip()
            if text.replace('.','',1).isdigit():
                numerical_values.add(text)

        # Create value entities for standalone numerical data
        for idx, value in enumerate(numerical_values):
            value_entity = KGEntity(
                id=f"value_{component_data.metadata.name}_{idx}",
                type="Value",
                properties={
                    "value": value,
                    "unit": "unknown",
                    "source": "documentation"
                }
            )
            entities.append(value_entity)
            relations.append(KGRelation(
                source_id=component_entity.id,
                target_id=value_entity.id,
                relation_type="has_value",
                properties={}
            ))
        
        return KGResult(
            entities=entities,
            relations=relations,
            source_component=component_data.metadata.name,
            extraction_metadata={
                "method": "manual_fallback"
            }
        )

    def _extract_kg_data(self,
                       graph_store: SimpleGraphStore,
                       component_name: str) -> Tuple[List[KGEntity], List[KGRelation]]:
        """Extract entities and relations from the graph store.
        
        Args:
            graph_store: The populated graph store
            component_name: Name of the component being processed
            
        Returns:
            Tuple of (entities, relations) extracted from the graph
        """
        entities = []
        relations = []
        
        try:
            # Get all triples from the graph store
            logger.debug("Getting triples from graph store")
            triples = graph_store.get(subj="")
            logger.debug(f"Found {len(triples)} triples in graph store")
            
            if not triples:
                logger.warning("No triples found in graph store")
                return [], []
            
            # Track unique nodes and their properties
            nodes = {}
            edges = []
            
            # Parse triples into nodes and edges
            for subj, rel, obj in triples:
                # Add subject node
                if subj not in nodes:
                    nodes[subj] = {"type": "Unknown", "properties": {}}
                
                # Add object node 
                if obj not in nodes:
                    nodes[obj] = {"type": "Unknown", "properties": {}}
                
                # If this is a type relation, update node type
                if rel == "type":
                    nodes[subj]["type"] = obj
                else:
                    # Otherwise it's a relationship between nodes
                    edges.append((subj, rel, obj))
            
            # Create KGEntity objects
            for node_id, node_data in nodes.items():
                entities.append(KGEntity(
                    id=str(node_id),
                    type=node_data["type"],
                    properties=node_data["properties"]
                ))
            
            # Create KGRelation objects
            for source_id, rel_type, target_id in edges:
                relations.append(KGRelation(
                    source_id=str(source_id),
                    target_id=str(target_id),
                    relation_type=rel_type,
                    properties={}
                ))
            
            return entities, relations
            
        except Exception as e:
            logger.error(f"Failed to extract KG data: {e}", exc_info=True)
            return [], []
