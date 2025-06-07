import asyncio
from graph_rag.crawler.component_crawler import ComponentCrawler
from graph_rag.crawler.page_handler import PageHandler
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
    
    # Initialize page handler and component crawler
    page_handler = PageHandler()
    crawler = ComponentCrawler(page_handler)
    
    # First phase: Discover all links for debugging
    logger.info("Phase 1: Discovering all component links...")
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=config.HEADLESS)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        
        try:
            # Navigate to start URL
            logger.info(f"Navigating to start URL: {config.START_URL}")
            await page_handler.navigate_to_component(page, config.START_URL)
            
            # Discover components
            logger.info("Discovering components...")
            discovered_components = await crawler.discover_components(page)
            
            # Deduplicate components by URL
            seen_urls = set()
            components = []
            for component in discovered_components:
                if component.url not in seen_urls:
                    components.append(component)
                    seen_urls.add(component.url)
                else:
                    logger.info(f"Skipping duplicate URL: {component.url}")
            
            # Print all discovered links for debugging
            logger.info(f"DISCOVERED {len(discovered_components)} COMPONENTS (before deduplication)")
            logger.info(f"UNIQUE COMPONENTS: {len(components)} (after deduplication)")
            logger.info("=" * 60)
            for i, component in enumerate(components, 1):
                logger.info(f"{i:2d}. Name: {component.name}")
                logger.info(f"    URL:  {component.url}")
                logger.info("-" * 40)
            logger.info("=" * 60)
            
            # Second phase: Process each discovered component
            logger.info("\nPhase 2: Processing discovered components...")
            for i, component in enumerate(components):
                logger.info(f"Processing component {i+1}/{len(components)}: {component.name}")
                try:
                    component_data = await crawler.process_component(component, page)
                    await crawler.save_component_data(component_data)
                    logger.info(f"✓ Saved data for {component.name}")
                except Exception as e:
                    logger.error(f"✗ Failed to process component {component.name}: {str(e)}")
        
        finally:
            # Clean up
            await browser.close()
    
    logger.info("Crawling completed")

if __name__ == "__main__":
    asyncio.run(main())