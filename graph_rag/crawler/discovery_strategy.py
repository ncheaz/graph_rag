from playwright.async_api import Page, Locator
from typing import List, Optional
from graph_rag.crawler.component import Component
from graph_rag.crawler.discovery_config import DiscoveryConfig
import re

class DiscoveryStrategy:
    """Base class for component discovery strategies."""
    
    def __init__(self, config: Optional[DiscoveryConfig] = None):
        self.config = config or DiscoveryConfig()
    
    async def discover_components(self, page: Page) -> List[Component]:
        raise NotImplementedError

class StorybookDiscoveryStrategy(DiscoveryStrategy):
    """Discovers components in a Storybook site."""
    
    async def discover_components(self, page: Page) -> List[Component]:
        """Discovers components from Storybook explorer tree."""
        components = []
        
        # Wait for navigation tree to load
        await page.wait_for_selector('#storybook-explorer-tree', timeout=self.config.discovery_timeout*1000)
        
        # Find all links in explorer tree
        links = []
        for selector in self.config.component_selectors:
            selector_links = await page.locator(selector).all()
            links.extend(selector_links)
        
        for link in links:
            href = await link.get_attribute('href')
            if href and self.config.url_patterns:
                for pattern in self.config.url_patterns:
                    if re.search(pattern, href):
                        components.append(Component(
                            name=await link.text_content() or f"Component {len(components)+1}",
                            url=page.url + href if not href.startswith('http') else href,
                            selectors=[str(link)]
                        ))
                        break
        
        return components