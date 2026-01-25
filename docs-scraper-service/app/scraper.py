"""Main scraper implementation using Playwright."""

from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
import asyncio
from app.config import settings
from app.converter import html_to_markdown, sanitize_filename
import logging

logger = logging.getLogger(__name__)


class DocsScraper:
    """Universal documentation scraper."""
    
    def __init__(
        self,
        base_url: str,
        project_name: str,
        url_filter: Optional[str] = None,
        max_depth: int = 10,
        follow_external: bool = False
    ):
        """
        Initialize scraper.
        
        Args:
            base_url: Base URL to start scraping from
            project_name: Name of the project (used for storage)
            url_filter: Optional filter pattern for URLs (e.g., '/docs')
            max_depth: Maximum depth to follow links
            follow_external: Whether to follow external links
        """
        self.base_url = base_url.rstrip('/')
        self.project_name = project_name
        self.url_filter = url_filter
        self.max_depth = max_depth
        self.follow_external = follow_external
        
        self.visited_urls: Set[str] = set()
        self.pages_data: List[Dict] = []
        self.failed_urls: List[str] = []
        
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
    
    def _should_visit(self, url: str) -> bool:
        """Check if URL should be visited."""
        # Already visited
        if url in self.visited_urls:
            return False
        
        # Parse URL
        parsed = urlparse(url)
        base_parsed = urlparse(self.base_url)
        
        # Check if external
        if not self.follow_external:
            if parsed.netloc and parsed.netloc != base_parsed.netloc:
                return False
        
        # Check filter
        if self.url_filter:
            if self.url_filter not in parsed.path:
                return False
        
        return True
    
    async def _extract_links(self, page: Page) -> List[str]:
        """Extract all links from current page."""
        links = await page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a[href]'));
            return links.map(link => link.href);
        }""")
        
        # Normalize and filter links
        normalized_links = []
        for link in links:
            try:
                # Handle relative URLs
                full_url = urljoin(self.base_url, link)
                # Remove fragments
                full_url = full_url.split('#')[0]
                
                if self._should_visit(full_url):
                    normalized_links.append(full_url)
            except Exception as e:
                logger.warning(f"Error processing link {link}: {e}")
        
        return list(set(normalized_links))  # Remove duplicates
    
    async def _extract_page_content(self, page: Page, url: str) -> Optional[Dict]:
        """Extract content from a page."""
        try:
            # Wait for main content
            await page.wait_for_selector(
                'main, article, [role="main"], body',
                timeout=settings.DEFAULT_TIMEOUT
            )
            
            # Extract title and content
            page_data = await page.evaluate("""() => {
                const titleEl = document.querySelector('h1') || 
                               document.querySelector('title') ||
                               document.querySelector('[data-title]');
                const title = titleEl ? titleEl.textContent.trim() : 'Untitled';
                
                const mainContent = document.querySelector('main') || 
                                   document.querySelector('article') ||
                                   document.querySelector('[role="main"]') ||
                                   document.body;
                
                return {
                    title: title,
                    html: mainContent.innerHTML,
                    url: window.location.href
                };
            }""")
            
            # Convert to markdown
            markdown = html_to_markdown(page_data['html'], url)
            
            # Generate filename
            parsed_url = urlparse(url)
            path_parts = [p for p in parsed_url.path.split('/') if p]
            
            if path_parts:
                filename_base = path_parts[-1] or 'index'
            else:
                filename_base = 'index'
            
            filename = sanitize_filename(filename_base)
            if not filename.endswith('.md'):
                filename += '.md'
            
            return {
                'title': page_data['title'],
                'content': f"# {page_data['title']}\n\n**URL:** {url}\n\n---\n\n{markdown}",
                'url': url,
                'filename': filename
            }
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None
    
    async def scrape(self) -> Dict:
        """Main scraping method."""
        async with async_playwright() as p:
            # Launch browser
            self.browser = await p.chromium.launch(
                headless=settings.HEADLESS,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            self.context = await self.browser.new_context(
                viewport={
                    'width': settings.VIEWPORT_WIDTH,
                    'height': settings.VIEWPORT_HEIGHT
                },
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            # Start with base URL
            urls_to_visit = [self.base_url]
            depth = 0
            
            while urls_to_visit and depth < self.max_depth:
                current_batch = urls_to_visit[:settings.MAX_CONCURRENT]
                urls_to_visit = urls_to_visit[settings.MAX_CONCURRENT:]
                
                # Process batch concurrently
                tasks = [self._process_url(url) for url in current_batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Collect new links from successful pages
                for result in results:
                    if isinstance(result, dict) and 'links' in result:
                        new_links = [link for link in result['links'] 
                                   if self._should_visit(link)]
                        urls_to_visit.extend(new_links)
                
                depth += 1
                
                # Small delay between batches
                if urls_to_visit:
                    await asyncio.sleep(settings.DEFAULT_WAIT_TIME / 1000)
            
            # Close browser
            await self.browser.close()
            
            return {
                'success': len(self.pages_data),
                'failed': len(self.failed_urls),
                'pages': self.pages_data,
                'failed_urls': self.failed_urls
            }
    
    async def _process_url(self, url: str) -> Dict:
        """Process a single URL."""
        if not self._should_visit(url):
            return {}
        
        self.visited_urls.add(url)
        page = await self.context.new_page()
        
        try:
            logger.info(f"Processing: {url}")
            
            await page.goto(url, wait_until='networkidle', timeout=settings.DEFAULT_TIMEOUT)
            
            # Extract content
            content = await self._extract_page_content(page, url)
            
            if content:
                self.pages_data.append(content)
            
            # Extract links
            links = await self._extract_links(page)
            
            await page.close()
            
            # Delay between requests
            await asyncio.sleep(settings.DEFAULT_WAIT_TIME / 1000)
            
            return {'links': links, 'content': content}
            
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            self.failed_urls.append(url)
            await page.close()
            return {'links': [], 'content': None}
