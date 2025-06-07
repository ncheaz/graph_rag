import json
import os
from playwright.async_api import Page, Locator
from typing import List, Dict, Any, Optional
from config import config
import aiofiles
from pydantic import BaseModel
from datetime import datetime
from abc import ABC, abstractmethod

from graph_rag.crawler.discovery_config import DiscoveryConfig
class Component(BaseModel):
    """Represents a design system component."""
    name: str
    url: str
    selectors: List[str]
    metadata: Dict[str, Any] = {}

class DiscoveryStrategy(ABC):
    """Abstract base class for component discovery strategies."""
    
    @abstractmethod
    async def discover_components(self, page: Page) -> List[Component]:
        """Discover components from the given page."""
        pass

class SelectorDiscoveryStrategy(DiscoveryStrategy):
    """Discovers components using CSS selectors."""
    
    def __init__(self, discovery_config: Optional[DiscoveryConfig] = None):
        self.config = discovery_config or DiscoveryConfig()
        self.selectors = self.config.component_selectors
        self.url_patterns = self.config.url_patterns or []
    
    async def discover_components(self, page: Page) -> List[Component]:
        """Discover components from storybook explorer tree."""
        components = []
        
        try:
            # Wait for explorer tree to be visible
            tree = page.locator('#storybook-explorer-tree')
            await tree.wait_for(state='visible', timeout=self.config.discovery_timeout * 1000)
            
            # Find all links in explorer tree
            links = await tree.locator('a[href]').all()
            
            # Also find expandable items that may contain nested links
            expandable_items = await tree.locator('[data-nodetype="group"]').all()
            for item in expandable_items:
                try:
                    await item.click()
                    nested_links = await tree.locator('a[href]').all()
                    links.extend(nested_links)
                except Exception as e:
                    print(f"Warning: Could not expand item - {str(e)}")
                    continue
            
            # Process all found links
            for link in links:
                try:
                    href = await link.get_attribute('href')
                    if not href:
                        continue
                    
                    # Create component from href
                    component = Component(
                        name=await link.text_content() or href,
                        url=href,
                        selectors=[str(link)]
                    )
                    components.append(component)
                except Exception as e:
                    print(f"Warning: Could not process link - {str(e)}")
                    continue
        except Exception as e:
            print(f"Error during component discovery: {str(e)}")
            raise
        
        return components

class ComponentData(BaseModel):
    """Structured data of a design system component."""
    name: str
    url: str
    html: str
    metadata: Dict[str, Any]
    discovered_at: str
    processed_at: str

class ComponentCrawler:
    """Discovers and processes design system components."""
    
    def __init__(self, page_handler, discovery_strategy: Optional[DiscoveryStrategy] = None, discovery_config: Optional[DiscoveryConfig] = None):
        self.page_handler = page_handler
        self.discovery_strategy = discovery_strategy or SelectorDiscoveryStrategy(discovery_config)

    async def run(self):
        """Run the entire crawling process."""
        from playwright.async_api import async_playwright
        from config import config
        import logging
        logger = logging.getLogger("crawler")
        
        logger.info(f"Using configuration: {config.to_dict()}")

        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=config.HEADLESS)
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()
            
            try:
                # Navigate to start URL
                logger.info(f"Navigating to start URL: {config.START_URL}")
                await self.page_handler.navigate_to_component(page, config.START_URL)
                
                # Discover components
                logger.info("Discovering components...")
                components = await self.discover_components(page)
                logger.info(f"Discovered {len(components)} components")
                
                # Process and save each component
                for i, component in enumerate(components):
                    logger.info(f"Processing component {i+1}/{len(components)}: {component.name}")
                    try:
                        component_data = await self.process_component(component, page)
                        await self.save_component_data(component_data)
                        logger.info(f"Saved data for {component.name}")
                    except Exception as e:
                        logger.error(f"Failed to process component {component.name}: {str(e)}")
            
            finally:
                # Clean up
                await browser.close()
    
    async def discover_components(self, page: Page) -> List[Component]:
        """
        Identifies components using the configured discovery strategy.
        
        :param page: Playwright page instance
        :return: List of discovered components
        """
        return await self.discovery_strategy.discover_components(page)
    
    async def process_component(self, component: Component, page: Page) -> ComponentData:
        """
        Extracts component data and relationships.
        
        :param component: Target component
        :param page: Playwright page instance
        :return: Structured component data
        """
        # Navigate to component page
        await self.page_handler.navigate_to_component(page, component.url)
        
        # Extract page content
        content = await self.page_handler.extract_page_content(page)
        
        return ComponentData(
            name=component.name,
            url=component.url,
            html=content.get("html", ""),
            metadata=content.get("metadata", {}),
            discovered_at=datetime.utcnow().isoformat(),
            processed_at=datetime.utcnow().isoformat()
        )
    
    async def save_component_data(self, component_data: ComponentData) -> None:
        """Saves component data to JSON file in output directory."""
        # Ensure output directory exists
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        
        # Create filename-safe component name
        safe_name = "".join(c if c.isalnum() else "_" for c in component_data.name)
        filename = f"{safe_name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.json"
        filepath = os.path.join(config.OUTPUT_DIR, filename)
        
        # Write data as JSON
        async with aiofiles.open(filepath, "w") as f:
            await f.write(component_data.json())