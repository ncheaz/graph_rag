import json
from playwright.async_api import Page
from typing import Any, Dict
from bs4 import BeautifulSoup
from config import config

class PageHandler:
    """Handles page interactions and navigation."""
    
    async def navigate_to_component(self, page: Page, component_url: str) -> None:
        """
        Navigates to a component page with minimal waiting.
        
        :param page: Playwright page instance
        :param component_url: URL of the component page
        """
        try:
            # Load page with short timeout
            await page.goto(component_url, timeout=5000)
            
            # Wait for basic DOM readiness
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
            
        except Exception as e:
            print(f"Warning: {str(e)} - proceeding with current page state")
    
    async def extract_page_content(self, page: Page) -> Dict[str, Any]:
        """
        Extracts content from storybook preview iframe after ensuring it's loaded.
        
        :param page: Playwright page instance
        :return: Dictionary of page content and metadata
        """
        # Wait for iframe to load
        try:
            frame = page.frame('storybook-preview-iframe')
            if not frame:
                raise Exception("Storybook preview iframe not found")
                
            await frame.wait_for_load_state('networkidle', timeout=10000)
            iframe_html = await frame.content()
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(iframe_html, 'html.parser')
            
            # Extract metadata from main page
            main_html = await page.content()
            main_soup = BeautifulSoup(main_html, 'html.parser')
            metadata = self.extract_metadata(main_soup)
            
            return {
                "url": page.url,
                "html": iframe_html,
                "metadata": metadata,
                "title": await page.title()
            }
            
        except Exception as e:
            print(f"Error extracting iframe content: {str(e)}")
            return {
                "url": page.url,
                "html": "",
                "metadata": {},
                "title": await page.title()
            }
        
        return {
            "url": page.url,
            "html": combined_html,
            "metadata": metadata,
            "title": await page.title()
        }
    
    def extract_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extracts metadata from the page."""
        metadata = {}
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = tag.get('name') or tag.get('property') or tag.get('itemprop')
            if name:
                metadata[name] = tag.get('content', '')
        return metadata