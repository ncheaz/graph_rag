import asyncio
from graph_rag.crawler.storybook_crawler import StorybookCrawler
import logging
import shutil
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crawler")

async def main():
    """Main entry point for the GraphRAG crawler."""
    logger.info("Starting GraphRAG crawler")
    
    from config import config
    logger.info(f"Configuration: {config.to_dict()}")
    
    # Clear previous crawl results
    process_dir = "process/crawler"
    if os.path.exists(process_dir):
        shutil.rmtree(process_dir)
        os.makedirs(process_dir)
        logger.info(f"Cleared directory: {process_dir}")
    
    # Initialize crawler
    crawler = StorybookCrawler()
    
    # Discover links
    links = await crawler.discover_links()
    logger.info(f"Discovered {len(links)} links")
    for link in links:
        logger.info(f"- {link}")

if __name__ == "__main__":
    asyncio.run(main())