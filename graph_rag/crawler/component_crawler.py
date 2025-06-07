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
        discovered_urls = set()  # Track unique URLs to avoid duplicates during discovery
        
        try:
            # Wait for explorer tree to be visible
            tree = page.locator('#storybook-explorer-tree')
            await tree.wait_for(state='visible', timeout=self.config.discovery_timeout * 1000)
            
            # Recursively expand all collapsible elements to reveal all nested components
            await self._expand_all_hierarchies(tree, page)
            
            # Wait for all expansions to stabilize
            await page.wait_for_timeout(2000)
            
            # Now find all links in the fully expanded explorer tree
            all_links = await tree.locator('a[href]').all()
            print(f"Found {len(all_links)} total links after expansion")
            
            # Process all found links
            for i, link in enumerate(all_links):
                try:
                    href = await link.get_attribute('href')
                    if not href:
                        continue
                    
                    # Skip if we've already discovered this URL
                    if href in discovered_urls:
                        continue
                    
                    # Get link text for component name
                    name = await link.text_content()
                    if not name:
                        name = href
                    
                    # Clean up name
                    name = name.strip()
                    if not name:
                        name = f"Component_{i}"
                    
                    # Create component from href
                    component = Component(
                        name=name,
                        url=href,
                        selectors=[str(link)]
                    )
                    components.append(component)
                    discovered_urls.add(href)
                    print(f"Discovered: {name} -> {href}")
                    
                except Exception as e:
                    print(f"Warning: Could not process link {i} - {str(e)}")
                    continue
        except Exception as e:
            print(f"Error during component discovery: {str(e)}")
            raise
        
        print(f"Total unique components discovered: {len(components)}")
        return components
    
    async def _expand_all_hierarchies(self, tree, page):
        """Recursively expand all hierarchical elements until no more can be expanded."""
        max_iterations = 15  # Increased to handle deep hierarchies
        iteration = 0
        
        # Set shorter timeout for faster operations during expansion
        page.set_default_timeout(1000)  # 1 second
        
        try:
            while iteration < max_iterations:
                iteration += 1
                print(f"Expansion iteration {iteration}")
                
                # Find all currently expandable elements (both groups and components)
                # The aria-expanded attribute is on the button element inside the div
                # Groups: div[data-nodetype="group"] > button[aria-expanded="false"]
                # Components: div[data-nodetype="component"] > button[aria-expanded="false"]
                expandable_groups = await tree.locator('[data-nodetype="group"] button[aria-expanded="false"]').all()
                expandable_components = await tree.locator('[data-nodetype="component"] button[aria-expanded="false"]').all()
                
                all_expandable = expandable_groups + expandable_components
                
                if not all_expandable:
                    print(f"No more expandable elements found. Stopping after {iteration} iterations.")
                    break
                    
                print(f"Found {len(all_expandable)} expandable elements ({len(expandable_groups)} groups, {len(expandable_components)} components)")
                
                # Expand all found elements
                expanded_count = 0
                for i, item in enumerate(all_expandable):
                    try:
                        # Try to click the element directly without checking aria-expanded first
                        # The element was already identified as expandable, so just click it
                        await item.click()
                        expanded_count += 1
                        print(f"  ✓ Expanded element {i+1}/{len(all_expandable)}")
                        # Small delay between expansions
                        await page.wait_for_timeout(150)
                    except Exception as e:
                        print(f"  ✗ Could not expand element {i+1}/{len(all_expandable)} - {str(e)}")
                        # If clicking failed, try to get some debug info
                        try:
                            node_type = await item.locator('..').get_attribute('data-nodetype')
                            item_id = await item.locator('..').get_attribute('data-item-id')
                            print(f"    Failed element info: nodetype={node_type}, item-id={item_id}")
                        except:
                            pass
                        continue
                
                print(f"Expanded {expanded_count}/{len(all_expandable)} elements in iteration {iteration}")
                
                # Wait for DOM updates after this round of expansions
                await page.wait_for_timeout(1500)
                
                # If we didn't expand anything, we're done
                if expanded_count == 0:
                    print(f"No elements were expanded in iteration {iteration}. Stopping.")
                    break
                
                # Show progress: how many total links are visible now
                current_links = await tree.locator('a[href]').count()
                print(f"  Current total links visible: {current_links}")
            
            if iteration >= max_iterations:
                print("Warning: Reached maximum iterations for hierarchy expansion")
            
        finally:
            # Reset timeout to default
            page.set_default_timeout(30000)
        
        # Final check: count total expandable elements that might still be collapsed
        remaining_groups = await tree.locator('[data-nodetype="group"] button[aria-expanded="false"]').count()
        remaining_components = await tree.locator('[data-nodetype="component"] button[aria-expanded="false"]').count()
        
        if remaining_groups > 0 or remaining_components > 0:
            print(f"Warning: {remaining_groups + remaining_components} elements remain unexpanded ({remaining_groups} groups, {remaining_components} components)")
        else:
            print("All hierarchies successfully expanded!")

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