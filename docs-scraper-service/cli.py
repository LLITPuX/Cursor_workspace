"""CLI interface for docs scraper."""

import asyncio
import argparse
import sys
from pathlib import Path
from app.scraper import DocsScraper
from app.storage import Storage
from app.config import settings


async def scrape_command(args):
    """Execute scraping command."""
    print(f"Starting scrape of {args.url}...")
    print(f"Project: {args.project}")
    print(f"Filter: {args.filter or 'None'}")
    print(f"Max depth: {args.depth}")
    print(f"Follow external: {args.external}\n")
    
    scraper = DocsScraper(
        base_url=args.url,
        project_name=args.project,
        url_filter=args.filter,
        max_depth=args.depth,
        follow_external=args.external
    )
    
    result = await scraper.scrape()
    
    # Save all pages
    storage = Storage()
    for page in result['pages']:
        await storage.save_document(
            project_name=args.project,
            filename=page['filename'],
            content=page['content'],
            metadata={'url': page['url'], 'title': page['title']}
        )
        print(f"  ✓ Saved: {page['filename']}")
    
    # Save index
    await storage.save_index(args.project, result['pages'])
    print(f"\n  ✓ Saved: INDEX.md")
    
    print(f"\n✅ Scraping completed!")
    print(f"   Success: {result['success']} pages")
    print(f"   Failed: {result['failed']} pages")
    
    if result['failed_urls']:
        print(f"\n   Failed URLs:")
        for url in result['failed_urls']:
            print(f"     - {url}")


def list_projects_command(args):
    """List all projects."""
    storage = Storage()
    projects = storage.list_projects()
    
    if not projects:
        print("No projects found.")
        return
    
    print("Projects:")
    for project in projects:
        files = storage.list_project_files(project)
        print(f"  - {project} ({len(files)} files)")


def list_files_command(args):
    """List files in a project."""
    storage = Storage()
    files = storage.list_project_files(args.project)
    
    if not files:
        print(f"No files found in project '{args.project}'.")
        return
    
    print(f"Files in '{args.project}':")
    for file in files:
        print(f"  - {file.name}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Docs Scraper CLI")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Scrape command
    scrape_parser = subparsers.add_parser('scrape', help='Scrape documentation')
    scrape_parser.add_argument('url', help='Base URL to scrape')
    scrape_parser.add_argument('--project', required=True, help='Project name')
    scrape_parser.add_argument('--filter', help='URL filter pattern (e.g., /docs)')
    scrape_parser.add_argument('--depth', type=int, default=10, help='Max depth (default: 10)')
    scrape_parser.add_argument('--external', action='store_true', help='Follow external links')
    
    # List projects command
    list_projects_parser = subparsers.add_parser('list-projects', help='List all projects')
    
    # List files command
    list_files_parser = subparsers.add_parser('list-files', help='List files in a project')
    list_files_parser.add_argument('project', help='Project name')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'scrape':
        asyncio.run(scrape_command(args))
    elif args.command == 'list-projects':
        list_projects_command(args)
    elif args.command == 'list-files':
        list_files_command(args)


if __name__ == '__main__':
    main()
