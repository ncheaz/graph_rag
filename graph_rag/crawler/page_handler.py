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
            # Handle relative URLs by building absolute URL
            if component_url.startswith('/') or component_url.startswith('?'):
                base_url = page.url.split('?')[0].split('#')[0]  # Get base URL without query/fragment
                if component_url.startswith('?'):
                    full_url = f"{base_url}{component_url}"
                else:
                    # For paths starting with /
                    from urllib.parse import urljoin
                    full_url = urljoin(base_url, component_url)
            elif component_url.startswith('#'):
                # For hash fragments, stay on current page
                full_url = page.url.split('#')[0] + component_url
            else:
                full_url = component_url
            
            print(f"Navigating to: {full_url}")
            
            # Load page with reasonable timeout
            await page.goto(full_url, timeout=10000)
            
            # Wait for basic DOM readiness
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            # Wait a bit more for iframe to load
            await page.wait_for_timeout(2000)
            
            print(f"Successfully navigated to: {full_url}")
            
        except Exception as e:
            print(f"Warning: {str(e)} - proceeding with current page state")
    
    async def extract_page_content(self, page: Page) -> Dict[str, Any]:
        """
        Extracts content from storybook preview iframe after ensuring it's loaded.
        
        :param page: Playwright page instance
        :return: Dictionary of page content and metadata
        """
        try:
            # Wait for the iframe to be present
            print("Looking for storybook-preview-iframe...")
            iframe_locator = page.locator('#storybook-preview-iframe')
            await iframe_locator.wait_for(state='attached', timeout=10000)
            print("Iframe found!")
            
            # Get the iframe frame object
            frame = page.frame('storybook-preview-iframe')
            if not frame:
                print("Warning: Storybook preview iframe not found")
                return {
                    "url": page.url,
                    "html": "",
                    "metadata": {},
                    "title": await page.title()
                }
            
            print("Waiting for iframe content to load...")
            # Wait for iframe content to load
            await frame.wait_for_load_state('domcontentloaded', timeout=10000)
            
            # Extract HTML content from iframe
            iframe_html = await frame.content()
            print(f"Extracted iframe HTML: {len(iframe_html)} characters")
            
            # Extract metadata from main page
            main_html = await page.content()
            main_soup = BeautifulSoup(main_html, 'html.parser')
            metadata = self.extract_metadata(main_soup)
            
            # Add component-specific metadata from iframe
            iframe_soup = BeautifulSoup(iframe_html, 'html.parser')
            iframe_metadata = self.extract_metadata(iframe_soup)
            metadata.update(iframe_metadata)
            print(f"Extracted metadata: {len(metadata)} items")
            
            # Extract additional component information
            metadata.update({
                "page_title": await page.title(),
                "iframe_title": await frame.title() if frame else "",
                "component_html_length": len(iframe_html),
                "has_iframe_content": bool(iframe_html.strip())
            })
            
            return {
                "url": page.url,
                "html": iframe_html,
                "metadata": metadata,
                "title": await page.title()
            }
            
        except Exception as e:
            print(f"Error extracting iframe content: {str(e)}")
            # Fallback to main page content if iframe fails
            try:
                main_html = await page.content()
                main_soup = BeautifulSoup(main_html, 'html.parser')
                metadata = self.extract_metadata(main_soup)
                
                return {
                    "url": page.url,
                    "html": main_html,
                    "metadata": metadata,
                    "title": await page.title()
                }
            except Exception as fallback_error:
                print(f"Fallback extraction also failed: {str(fallback_error)}")
                return {
                    "url": page.url,
                    "html": "",
                    "metadata": {},
                    "title": ""
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