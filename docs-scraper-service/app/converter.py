"""HTML to Markdown converter."""

from markdownify import markdownify as md
from bs4 import BeautifulSoup
import re


def clean_html(html: str) -> str:
    """Remove unwanted elements from HTML."""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove unwanted elements
    unwanted_selectors = [
        'nav', 'header', 'footer',
        '[role="navigation"]',
        '[role="banner"]',
        '[role="contentinfo"]',
        '.sidebar', '.navigation', '.nav',
        'script', 'style', 'noscript',
        '.cookie-banner', '.advertisement'
    ]
    
    for selector in unwanted_selectors:
        for element in soup.select(selector):
            element.decompose()
    
    return str(soup)


def html_to_markdown(html: str, base_url: str = "") -> str:
    """Convert HTML to Markdown."""
    # Clean HTML first
    cleaned_html = clean_html(html)
    
    # Convert to markdown
    markdown = md(
        cleaned_html,
        heading_style="ATX",
        bullets="-",
        strip=['script', 'style']
    )
    
    # Fix relative URLs if base_url provided
    if base_url:
        markdown = fix_relative_urls(markdown, base_url)
    
    return markdown.strip()


def fix_relative_urls(markdown: str, base_url: str) -> str:
    """Convert relative URLs to absolute in markdown."""
    # Pattern for markdown links: [text](url)
    def replace_link(match):
        text = match.group(1)
        url = match.group(2)
        
        # If URL is relative, make it absolute
        if url.startswith('/') and not url.startswith('//'):
            from urllib.parse import urljoin
            url = urljoin(base_url, url)
        
        return f"[{text}]({url})"
    
    # Replace markdown links
    markdown = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace_link, markdown)
    
    return markdown


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """Sanitize string for use as filename."""
    # Remove special characters, keep only alphanumeric, spaces, hyphens, underscores
    sanitized = re.sub(r'[^a-zA-Z0-9\s\-_]', '', name)
    # Replace spaces with hyphens
    sanitized = re.sub(r'\s+', '-', sanitized)
    # Remove multiple consecutive hyphens
    sanitized = re.sub(r'-+', '-', sanitized)
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip('-')
    # Limit length
    sanitized = sanitized[:max_length]
    # Convert to lowercase
    return sanitized.lower()
