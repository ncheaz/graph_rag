# Content Extraction Guide

## Overview

The extraction phase transforms raw HTML content from previously crawled Storybook pages into structured data suitable for knowledge graph storage. The input consists of JSON files stored in `process/crawler/` containing the crawled page data. This process extracts metadata, component information, relationships, and content using BeautifulSoup parsing with field-specific CSS selectors.

Consult with the implementation plan first to get a better idea of how extraction fits into the entire workflow.

Make sure to follow the guidelines in the blueprint GRAPH_RAG_CODE_BLUEPRINT.md

## Key Components

### 1. **MetadataExtractor**
   - Located in `extraction/metadata_extractor.py`
   - Uses CSS selectors and XPath for precise field extraction
   - Supports multi-source metadata aggregation from main page and iframe content

### 2. **Content Parser**
   - Processes component documentation and usage guidelines
   - Extracts code examples with syntax highlighting information
   - Handles dynamic content loaded in Storybook iframe

### 3. **Relationship Analyzer**
   - Maps component dependencies using AST-based analysis
   - Identifies related components through DOM structure analysis
   - Builds dependency graphs for component relationships

## Extraction Strategy

The system processes pre-crawled content stored in JSON files:

### Phase 1: JSON Data Processing
1. **Input Data Structure**
   - Read JSON files from `process/crawler/` directory
   - Each file contains: `name`, `url`, `html`, `metadata`, `title`
   - Process files sequentially or in batches for efficiency

2. **HTML Content Parsing**
   - Parse the `html` field from each JSON file using BeautifulSoup
   - Extract component-specific content from the stored HTML
   - Handle both documentation pages and interactive component examples

### Phase 2: Structured Data Extraction

#### Metadata Fields
Here is the information from our previous discussion about the LlamaIndex extraction strategy, formatted in the same style as the crawling.md file.

Schema-Guided Extraction Guide
Key Strategy
The extraction process uses a hybrid model to combine the strengths of traditional parsing and LLM-based semantic analysis.

HTML Pre-processing

Use BeautifulSoup with simple CSS selectors to isolate and clean relevant text blocks.
Extracts key segments like descriptions, usage guidelines, and props tables.
KG Extraction

Feed the clean, segmented text into llama_index.PropertyGraphIndex.
Uses a SchemaLLMPathExtractor to identify entities and relationships based on a predefined schema.
Core Technologies
Primary Framework: llama_index
Extraction Engine: SchemaLLMPathExtractor
Knowledge Graph Index: PropertyGraphIndex
HTML Parsing: BeautifulSoup
LLM: OpenAI models (gpt-4-turbo, gpt-3.5-turbo)
KG Schema
The LLM is guided by a strict schema to ensure consistency.

Entities (Nodes)

COMPONENT: A UI component, the central entity.
PROPERTY: A configurable property of a component.
VALUE_OPTION: A possible value for a component property.
DEFAULT_VALUE: The default value for a property.
DESIGN_TOKEN: A design token used by a component.
PURPOSE: The intended use or goal of a component.
GUIDELINE: A best practice or rule for using a component.
Relations (Edges)

HAS_PROPERTY: Connects a component to one of its properties.
HAS_OPTION: Connects a property to a possible value.
HAS_DEFAULT: Connects a property to its default value.
USES_TOKEN: Connects a component to a design token it uses.
HAS_PURPOSE: Describes the component's reason for existing.
HAS_GUIDELINE: Connects a component to its usage guidelines.
DEPENDS_ON: Connects a component to another it relies on.
Extraction Workflow
To effectively extract KG data from a component page:

Load the full source HTML provided by the crawler.
Use BeautifulSoup to pre-process the HTML, extracting and cleaning the main text content areas.
Combine the cleaned text into a single string and create a llama_index.core.Document.
Instantiate the SchemaLLMPathExtractor with the predefined KG schema and an LLM.
Build the PropertyGraphIndex from the Document object, using the extractor to populate a graph store.
Persist the populated graph store (e.g., KuzuGraphStore) for use by the query engine.
Important Notes
This approach focuses on the semantic meaning of text, not just its HTML structure.
The schema is critical for ensuring the consistency and precision of the extracted knowledge.
This method is more resilient to minor changes in website markup and styling.
The resulting structured graph enables powerful, precise queries about component relationships and usage.

The output of the extraction process is the process/extraction directory




