import logging
from playwright.async_api import Page, async_playwright
from typing import List
from config import config
from .discovery_config import DiscoveryConfig

logger = logging.getLogger("crawler")

class StorybookCrawler:
    def __init__(self):
        self.config = DiscoveryConfig()
    
    async def discover_links(self) -> List[str]:
        """Discover and return all unique links from expanded Storybook menus"""
        logger.info("Starting Storybook link discovery")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=config.HEADLESS)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Navigate to start URL
            await page.goto(config.START_URL)
            logger.info(f"Navigated to start URL: {config.START_URL}")
            
            try:
                # Wait for explorer menu to be visible
                await page.wait_for_selector(
                    "#storybook-explorer-menu",
                    state="visible",
                    timeout=self.config.discovery_timeout*1000
                )
                
                # First expand all top-level groups
                groups = await page.query_selector_all('#storybook-explorer-menu [data-nodetype="group"]')
                for group in groups:
                    try:
                        await group.click()
                        await page.wait_for_timeout(500)  # Wait for expansion
                    except Exception as e:
                        logger.warning(f"Could not expand group: {str(e)}")

                # Then expand all component menus
                component_menus = await page.query_selector_all('#storybook-explorer-menu [data-nodetype="component"]')
                for component in component_menus:
                    try:
                        await component.click()
                        await page.wait_for_timeout(500)  # Wait for expansion
                    except Exception as e:
                        logger.warning(f"Could not expand component: {str(e)}")

                # Wait for all menus to fully expand
                await page.wait_for_timeout(2000)

                # Now find all content links in the expanded menu
                anchors = await page.query_selector_all('#storybook-explorer-menu a[href]')
                seen_urls = set()
                links = []
                
                for anchor in anchors:
                    href = await anchor.get_attribute('href')
                    if not href or href.startswith('#'):
                        continue
                        
                    # Normalize URL
                    if not href.startswith('http'):
                        if href.startswith('/'):
                            href = f"{config.START_URL.rstrip('/')}{href}"
                        else:
                            href = f"{config.START_URL.rstrip('/')}/{href}"
                    
                    if href in seen_urls:
                        continue
                        
                    seen_urls.add(href)
                    links.append(href)
                    logger.info(f"Found link: {href}")
                
                logger.info(f"Found {len(links)} unique links")
                return links
                
            except Exception as e:
                logger.error(f"Link discovery failed: {str(e)}")
                return []
            
            finally:
                await browser.close()
