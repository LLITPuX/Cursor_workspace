"""Storage management for scraped documentation."""

from pathlib import Path
from typing import Optional
import aiofiles
from app.config import settings


class Storage:
    """Manages storage of scraped documentation."""
    
    def __init__(self, docs_root: Optional[Path] = None):
        """Initialize storage with docs root directory."""
        self.docs_root = docs_root or settings.DOCS_ROOT
        self.docs_root.mkdir(parents=True, exist_ok=True)
    
    def get_project_path(self, project_name: str) -> Path:
        """Get path for a specific project."""
        project_path = self.docs_root / project_name
        project_path.mkdir(parents=True, exist_ok=True)
        return project_path
    
    async def save_document(
        self,
        project_name: str,
        filename: str,
        content: str,
        metadata: Optional[dict] = None
    ) -> Path:
        """Save a document to storage."""
        project_path = self.get_project_path(project_name)
        file_path = project_path / filename
        
        # Add metadata header if provided
        if metadata:
            header = "---\n"
            for key, value in metadata.items():
                header += f"{key}: {value}\n"
            header += "---\n\n"
            content = header + content
        
        # Save file
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(content)
        
        return file_path
    
    async def save_index(
        self,
        project_name: str,
        pages: list[dict]
    ) -> Path:
        """Save index file with list of all pages."""
        project_path = self.get_project_path(project_name)
        index_path = project_path / "INDEX.md"
        
        from datetime import datetime
        
        content = f"""# {project_name.title()} Documentation Index

**Date scraped:** {datetime.now().isoformat()}

**Total pages:** {len(pages)}

## Pages

"""
        
        for i, page in enumerate(pages, 1):
            title = page.get('title', 'Untitled')
            filename = page.get('filename', 'unknown.md')
            url = page.get('url', '')
            content += f"{i}. [{title}]({filename}) - {url}\n"
        
        async with aiofiles.open(index_path, 'w', encoding='utf-8') as f:
            await f.write(content)
        
        return index_path
    
    def list_projects(self) -> list[str]:
        """List all projects in storage."""
        if not self.docs_root.exists():
            return []
        
        projects = [
            d.name for d in self.docs_root.iterdir()
            if d.is_dir() and not d.name.startswith('.')
        ]
        return sorted(projects)
    
    def list_project_files(self, project_name: str) -> list[Path]:
        """List all files in a project."""
        project_path = self.get_project_path(project_name)
        if not project_path.exists():
            return []
        
        return sorted([
            f for f in project_path.iterdir()
            if f.is_file() and f.suffix == '.md'
        ])
