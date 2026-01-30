"""Main scraper implementation using Playwright."""

from playwright.async_api import async_playwright, Browser, Page, BrowserContext
import re
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

    async def scrape_gemini_session(self, url: str, output_path: str, filename: Optional[str] = None) -> Dict:
        """
        Scrape a Gemini session and save as Markdown.
        
        Args:
            url: Public Gemini session URL
            output_path: Directory to save the file
            filename: Optional filename
            
        Returns:
            Dict with status and file path
        """
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(
                headless=settings.HEADLESS,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled']
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()
            
            try:
                logger.info(f"Navigating to Gemini session: {url}")
                # Use domcontentloaded instead of networkidle as it's more reliable for some SPA
                await page.goto(url, wait_until='domcontentloaded', timeout=90000)
                
                logger.info("DOM loaded, waiting 5s for JS rendering...")
                await asyncio.sleep(5)
                
                # Wait for content to load (look for user-query or model-response containers)
                # Gemini structure varies, checking for common elements
                try:
                    logger.info("Waiting for selectors...")
                    await page.wait_for_selector('message-content, .message-content, [data-test-id="user-query"], .query-content, .response-content', timeout=20000)
                except Exception as e:
                    logger.warning(f"Timeout waiting for selectors, proceeding anyway: {e}")
                
                # Debug: log the page content summary
                body_content = await page.evaluate("() => document.body.innerText.substring(0, 1000)")
                logger.info(f"Page body preview: {body_content}")

                # Scroll to bottom to ensure all content loads
                await page.evaluate("""async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 100;
                        const timer = setInterval(() => {
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if(totalHeight >= scrollHeight){
                                clearInterval(timer);
                                resolve();
                            }
                        }, 100);
                    });
                }""")
                
                # Extract Data
                session_data = await page.evaluate("""() => {
                    const noiseSelectors = [
                        'mat-sidenav', 
                        'nav', 
                        'aside', 
                        '.nav-drawer', 
                        '.sidebar',
                        '[role="navigation"]'
                    ];
                    noiseSelectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => el.remove());
                    });

                    const result = {
                        title: 'Unknown Session',
                        items: []
                    };
                    
                    // 1. Title Extraction
                    const titleEl = document.querySelector('h1') || 
                                   document.querySelector('h1.title') || 
                                   document.querySelector('.conversation-title') ||
                                   document.querySelector('title');
                    result.title = titleEl ? titleEl.textContent.trim() : 'Gemini Session';
                    
                    // 2. Identify the Main Chat Container (fallback to body if now clean)
                    const mainContainer = document.querySelector('mat-sidenav-content') ||
                                          document.querySelector('[role="main"]') ||
                                          document.querySelector('main') || 
                                          document.body;
                                          
                    // 3. Extraction Strategy
                    const selector = 'user-query, model-response, .query-content, .response-content, .message-content';
                    const turns = Array.from(mainContainer.querySelectorAll(selector));
                    
                    // Bad patterns that indicate UI noise (sidebar items, history)
                    const noisePatterns = [
                        /^Хронология/i,
                        /^History/i,
                        /^Arquiva/i,
                        /^Recent/i,
                        /NotebookLM/i,
                        /Cursor AI/i,
                        /Gem-bot/i
                    ];

                    const isValid = (el) => {
                         const text = el.innerText.trim();
                         if (!text) return false;
                         if (text.length < 3) return false;
                         
                         // Check for sidebar menu patterns (lists of short items)
                         if (noisePatterns.some(p => p.test(text)) && text.length < 50) return false;
                         
                         // Check if it's inside a navigation element
                         if (el.closest('nav') || el.closest('aside') || el.closest('.sidebar')) return false;
                         
                         return true;
                    };

                    if (turns.length > 0) {
                        turns.forEach(el => {
                            let role = 'unknown';
                            
                            // Determine role
                            const tagName = el.tagName.toLowerCase();
                            const classList = el.classList;
                            
                            if (tagName === 'user-query' || classList.contains('query-content')) {
                                role = 'user';
                            } else if (tagName === 'model-response' || classList.contains('response-content') || classList.contains('message-content')) {
                                role = 'model';
                            }
                            
                            // Text cleaning
                            let text = el.innerText.trim();
                            // Common Gemini UI noise removal
                            text = text.replace(/Show drafts|Regenerate drafts|volume_up|thumb_up|thumb_down|more_vert|Export to Sheets/g, '').trim();
                            
                            if (text && role !== 'unknown' && isValid(el)) {
                                result.items.push({ role, content: text });
                            }
                        });
                    }
                    
                    // Deduplication logic
                    const uniqueItems = [];
                    if (result.items.length > 0) {
                        uniqueItems.push(result.items[0]);
                        
                        for (let i = 1; i < result.items.length; i++) {
                            const current = result.items[i];
                            const prev = uniqueItems[uniqueItems.length - 1];
                            
                            // Exact duplicate
                            if (current.content === prev.content && current.role === prev.role) continue;
                            
                            // Nested content duplicate
                            if (current.role === prev.role) {
                                 if (prev.content.includes(current.content)) continue; 
                                 if (current.content.includes(prev.content)) {
                                     uniqueItems[uniqueItems.length - 1] = current;
                                     continue;
                                 }
                            }
                            
                            uniqueItems.push(current);
                        }
                    }
                    result.items = uniqueItems;
                    
                    return result;
                }""")
                
                # Post-processing: Clean noise via Regex on the Python side
                # The sidebar text often leaks into the first user message in shared views
                def clean_content_for_markdown(content: str) -> str:
                    """
                    Clean content for Markdown compatibility.
                    Removes UI artifacts, escapes HTML tags, and fixes table formatting.
                    """
                    if not content:
                        return content
                    
                    # Remove lines with "Export to Sheets" (case-insensitive)
                    lines = content.split('\n')
                    cleaned_lines = [line for line in lines if 'export to sheets' not in line.lower()]
                    content = '\n'.join(cleaned_lines)
                    
                    # Remove tables with tabulation (lines with tabs between words)
                    # Pattern: text\ttext (tab-separated columns)
                    # Also remove consecutive lines that look like table rows
                    lines = content.split('\n')
                    cleaned_lines = []
                    in_table = False
                    for i, line in enumerate(lines):
                        # Check if line contains tabulation between words (likely a table row)
                        # Also check if line looks like a table header/separator
                        is_table_row = False
                        if '\t' in line:
                            parts = line.split('\t')
                            # If line has 2+ tab-separated parts with text, it's a table row
                            if len(parts) >= 2 and any(p.strip() for p in parts):
                                is_table_row = True
                        
                        if is_table_row:
                            in_table = True
                            continue  # Skip this table row
                        
                        # If we were in a table and hit a non-table line, check if it's just spacing
                        if in_table:
                            # If next line is also a table row, continue skipping
                            if i + 1 < len(lines):
                                next_line = lines[i + 1]
                                if '\t' in next_line and len(next_line.split('\t')) >= 2:
                                    continue  # Still in table
                            # Otherwise, we're out of the table
                            in_table = False
                            # Skip empty line after table if present
                            if not line.strip():
                                continue
                        
                        cleaned_lines.append(line)
                    content = '\n'.join(cleaned_lines)
                    
                    # Escape HTML tags to prevent Markdown parsing issues
                    # Preserve code blocks and escape HTML tags outside them
                    def escape_html_tags(text: str) -> str:
                        # Find and temporarily replace code blocks
                        code_block_pattern = r'```[\s\S]*?```|`[^`\n]+`'
                        code_blocks = []
                        placeholder_template = "__CODE_BLOCK_{}__"
                        
                        def replace_with_placeholder(match):
                            idx = len(code_blocks)
                            code_blocks.append(match.group(0))
                            return placeholder_template.format(idx)
                        
                        # Replace code blocks with placeholders
                        text_with_placeholders = re.sub(code_block_pattern, replace_with_placeholder, text)
                        
                        # Escape HTML tags: <tag> -> &lt;tag&gt;
                        # Process text between placeholders to avoid breaking code blocks
                        escaped_text = text_with_placeholders
                        
                        # Find all placeholder positions
                        placeholder_positions = []
                        for match in re.finditer(r'__CODE_BLOCK_\d+__', escaped_text):
                            placeholder_positions.append((match.start(), match.end()))
                        
                        # Process text in segments, avoiding placeholders
                        result_parts = []
                        last_end = 0
                        
                        for start, end in placeholder_positions:
                            # Process text before placeholder
                            segment = escaped_text[last_end:start]
                            # Escape HTML tags in this segment
                            segment = re.sub(r'<([a-zA-Z][a-zA-Z0-9]*)(?:\s+[^>]*)?/?>', r'&lt;\1&gt;', segment)
                            segment = re.sub(r'</([a-zA-Z][a-zA-Z0-9]*)>', r'&lt;/\1&gt;', segment)
                            result_parts.append(segment)
                            
                            # Add placeholder unchanged
                            result_parts.append(escaped_text[start:end])
                            last_end = end
                        
                        # Process remaining text after last placeholder
                        if last_end < len(escaped_text):
                            segment = escaped_text[last_end:]
                            segment = re.sub(r'<([a-zA-Z][a-zA-Z0-9]*)(?:\s+[^>]*)?/?>', r'&lt;\1&gt;', segment)
                            segment = re.sub(r'</([a-zA-Z][a-zA-Z0-9]*)>', r'&lt;/\1&gt;', segment)
                            result_parts.append(segment)
                        
                        escaped_text = ''.join(result_parts)
                        
                        # Restore code blocks
                        for idx, code_block in enumerate(code_blocks):
                            escaped_text = escaped_text.replace(placeholder_template.format(idx), code_block)
                        
                        return escaped_text
                    
                    content = escape_html_tags(content)
                    
                    # Clean up multiple blank lines
                    content = re.sub(r'\n{3,}', '\n\n', content)
                    
                    return content.strip()
                
                # Clean all items, not just the first one
                if session_data['items']:
                    # Special handling for first user message (sidebar noise)
                    first_item = session_data['items'][0]
                    if first_item['role'] == 'user':
                        # Regex to matching the "Chronology..." sidebar block
                        cleaned_content = re.sub(
                            r'^(Хронология|History|Recent|Архив).*?NotebookLM.*?\n\n', 
                            '', 
                            first_item['content'], 
                            flags=re.DOTALL | re.IGNORECASE
                        )
                        # Fallback: if regular regex misses but we see the noise pattern
                        if "Хронология" in first_item['content'] and len(first_item['content']) < 1000:
                             lines = first_item['content'].split('\n')
                             # Filter out lines that look like menu items
                             clean_lines = [line for line in lines if not any(x in line for x in ['Хронология', 'NotebookLM', 'Cursor AI', 'Gem-bot', 'Архив'])]
                             if len(clean_lines) < len(lines):
                                 cleaned_content = '\n'.join(clean_lines).strip()
                        
                        first_item['content'] = cleaned_content.strip()
                        session_data['items'][0] = first_item
                    
                    # Clean all items for Markdown compatibility
                    for item in session_data['items']:
                        item['content'] = clean_content_for_markdown(item['content'])

                # Format Date
                from datetime import datetime
                import locale
                
                def generate_english_filename(title: str) -> str:
                    """
                    Generate English filename from title using transliteration.
                    Converts Cyrillic to Latin and creates snake_case filename.
                    """
                    # Simple transliteration dictionary for common Cyrillic characters
                    translit_map = {
                        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
                        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
                        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
                        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
                        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
                        'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
                        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
                        'і': 'i', 'ї': 'yi', 'є': 'ye', 'ґ': 'g',
                        'І': 'I', 'Ї': 'Yi', 'Є': 'Ye', 'Ґ': 'G'
                    }
                    
                    # Transliterate
                    result = []
                    for char in title:
                        if char in translit_map:
                            result.append(translit_map[char])
                        elif char.isalnum():
                            result.append(char)
                        else:
                            result.append('_')
                    
                    # Convert to snake_case and clean up
                    text = ''.join(result)
                    # Replace multiple underscores/spaces with single underscore
                    text = re.sub(r'[_\s]+', '_', text)
                    # Remove leading/trailing underscores
                    text = text.strip('_')
                    # Convert to lowercase
                    text = text.lower()
                    # Limit length
                    text = text[:50]
                    
                    return text if text else 'session'
                
                # Check if we can set locale to Ukrainian, otherwise use simple mapping
                months_ua = {
                    1: 'січня', 2: 'лютого', 3: 'березня', 4: 'квітня', 5: 'травня', 6: 'червня',
                    7: 'липня', 8: 'серпня', 9: 'вересня', 10: 'жовтня', 11: 'листопада', 12: 'грудня'
                }
                
                now = datetime.now()
                month_name = months_ua.get(now.month, now.strftime('%B'))
                date_str = f"{now.day} {month_name} {now.year}, {now.strftime('%H:%M:%S')}"
                
                # Build Markdown
                title = session_data.get('title', 'Gemini Session')
                if not filename:
                    # Generate English filename with timestamp
                    english_title = generate_english_filename(title)
                    timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')
                    # Sanitize only the title part, preserve timestamp format
                    safe_title = sanitize_filename(english_title)
                    filename = f"gemini_session_{timestamp}_{safe_title}.md"
                
                if not filename.endswith('.md'):
                    filename += '.md'
                    
                md_content = f"# Сесія: {title}\n\n"
                md_content += f"**Дата:** {date_str}\n"
                md_content += f"**Тема:** {title}\n\n"
                md_content += "---\n\n"
                
                items = session_data.get('items', [])
                
                user_count = 0
                model_count = 0
                
                for item in items:
                    role = item['role']
                    content = item['content']
                    
                    if role == 'user':
                        user_count += 1
                        md_content += f"## Запит користувача #{user_count}\n\n"
                        md_content += f"{content}\n\n"
                    else:
                        model_count += 1
                        md_content += f"### Відповідь #{model_count}\n\n"
                        md_content += f"{content}\n\n"
                
                # Save file
                import os
                full_path = os.path.join(output_path, filename)
                
                # Ensure directory exists
                os.makedirs(output_path, exist_ok=True)
                
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(md_content)
                
                await browser.close()
                
                return {
                    'success': True,
                    'file_path': full_path,
                    'message_count': len(items)
                }
                
            except Exception as e:
                logger.error(f"Error scraping Gemini session: {e}")
                await browser.close()
                raise e
