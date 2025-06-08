\
import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from graph_rag.extraction.extractor import ExtractionOrchestrator
from graph_rag.extraction.data_models import ExtractedComponent, ComponentMetadata, ComponentProperty, UsageGuideline, CodeExample, ComponentDependency # Changed Relationship to ComponentDependency

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '.env')
logger.info(f"Loading .env from: {env_path}")
if not load_dotenv(env_path):
    logger.warning(f"No .env file found at {env_path}")

# Debug log loaded environment variables
logger.debug("Environment variables:")
for k, v in os.environ.items():
    if 'KEY' in k or 'SECRET' in k:
        logger.debug(f"  {k}=[REDACTED]")
    else:
        logger.debug(f"  {k}={v}")

# Configure logging level and format
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Define paths
CRAWLER_OUTPUT_DIR = "./process/crawler/"
KG_OUTPUT_DIR = "./process/extraction/"

def load_crawler_data(file_path: str) -> Optional[dict]:
    """Loads a single JSON file from the crawler output."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Successfully loaded crawler data from: {file_path}")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading file {file_path}: {e}")
        return None

def save_kg_result(kg_result, original_filename: str):
    """Saves the KGResult to a JSON file in the KG_OUTPUT_DIR."""
    if not kg_result:
        logger.warning(f"No KG result to save for {original_filename}")
        return

    base_filename = os.path.splitext(original_filename)[0]
    output_filename = f"{base_filename}_kg.json"
    output_path = os.path.join(KG_OUTPUT_DIR, output_filename)

    try:
        # Convert KGResult to dict using its dict() method
        result_dict = kg_result.dict()


        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully saved KG result to: {output_path}")
    except TypeError as e:
        logger.error(f"TypeError saving KG result for {original_filename} to {output_path}. Ensure KGResult is JSON serializable: {e}")
        logger.error(f"KG Result data: {kg_result}")
    except Exception as e:
        logger.error(f"Error saving KG result for {original_filename} to {output_path}: {e}")


def main(max_docs: Optional[int] = None):
    logger.info("Starting KG extraction test process...")
    
    if not os.path.exists(CRAWLER_OUTPUT_DIR):
        logger.error(f"Crawler output directory not found: {CRAWLER_OUTPUT_DIR}")
        return
        
    if not os.path.exists(KG_OUTPUT_DIR):
        logger.warning(f"KG output directory not found: {KG_OUTPUT_DIR}. It will be created.")
        os.makedirs(KG_OUTPUT_DIR, exist_ok=True)

    # Initialize the orchestrator
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable is not set.")
        logger.error("Please create a .env file with OPENAI_API_KEY=your_key_here")
        logger.error("Or set the environment variable before running the script")
        return

    try:
        orchestrator = ExtractionOrchestrator()
    except Exception as e:
        logger.error(f"Failed to initialize ExtractionOrchestrator: {e}")
        return

    processed_files = 0
    failed_files = 0

    json_files = sorted([f for f in os.listdir(CRAWLER_OUTPUT_DIR) if f.endswith('.json')])
    if max_docs:
        json_files = json_files[:max_docs]
        logger.info(f"Limiting processing to first {max_docs} files")
    
    for filename in json_files:
            file_path = os.path.join(CRAWLER_OUTPUT_DIR, filename)
            logger.info(f"Processing file: {filename}")
            
            crawler_data = load_crawler_data(file_path)
            if not crawler_data:
                failed_files += 1
                continue

            html_content = crawler_data.get("html")
            component_name = crawler_data.get("name", "UnknownComponent")
            source_url = crawler_data.get("url", "")
            
            if not html_content:
                logger.warning(f"No HTML content found in {filename}. Skipping.")
                failed_files += 1
                continue
            
            try:
                # First, extract the base component data
                logger.info(f"Extracting base component data for {component_name} from {filename}...")
                # crawler_data is the dictionary loaded from the JSON file
                component_data = orchestrator.extract_component(crawler_data)

                logger.info(f"Attempting KG extraction for {component_name} using kg_extractor...")
                kg_result = orchestrator.kg_extractor.extract_knowledge_graph(
                    component_data=component_data,
                    html_content=html_content # html_content is already extracted from crawler_data
                )
                
                if kg_result:
                    save_kg_result(kg_result, filename)
                    processed_files += 1
                else:
                    logger.warning(f"KG extraction returned no result for {filename}.")
                    failed_files +=1
                    
            except Exception as e:
                logger.error(f"Error during KG extraction for {filename}: {e}", exc_info=True)
                failed_files += 1
                # Optionally save a placeholder or error file
                error_kg_result = {
                    "source_component": component_name,
                    "error": str(e),
                    "filename": filename
                }
                save_kg_result(error_kg_result, f"{os.path.splitext(filename)[0]}_error.json")


    logger.info(f"KG extraction process finished.")
    logger.info(f"Successfully processed files: {processed_files}")
    logger.info(f"Failed files: {failed_files}")
    logger.info(f"Output files created in: {KG_OUTPUT_DIR}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-docs", type=int, default=None,
                       help="Maximum number of documents to process")
    args = parser.parse_args()
    
    main(max_docs=args.max_docs)
