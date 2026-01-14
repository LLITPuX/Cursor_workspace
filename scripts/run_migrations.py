#!/usr/bin/env python3
"""
Migration runner for Neon database migrations.

This script automatically applies migrations from the migrations/ directory
in the correct order, tracking applied migrations in schema_migrations table.

Usage:
    python scripts/run_migrations.py [--dry-run] [--connection-string CONN_STR]
    
Environment:
    NEON_CONNECTION_STRING - Database connection string (required unless --connection-string provided)
"""
import os
import sys
import asyncio
import asyncpg
import hashlib
import time
from pathlib import Path
from typing import List, Tuple, Optional
import argparse
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get migrations directory
MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def get_migration_files() -> List[Tuple[str, Path]]:
    """Get all migration files sorted by version."""
    migrations = []
    
    for file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        # Extract version from filename (e.g., "003_schema_versioning.sql" -> "003")
        if file.name == "init.sql":
            migrations.append(("001", file))
        else:
            # Try to extract version from filename
            parts = file.stem.split("_", 1)
            if parts[0].isdigit():
                migrations.append((parts[0], file))
            else:
                logger.warning(f"Could not extract version from {file.name}, skipping")
    
    return sorted(migrations, key=lambda x: x[0])


def calculate_checksum(content: str) -> str:
    """Calculate SHA256 checksum of migration content."""
    return hashlib.sha256(content.encode()).hexdigest()


async def get_applied_migrations(conn: asyncpg.Connection) -> set:
    """Get set of applied migration versions."""
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    return {row['version'] for row in rows}


async def check_schema_migrations_table(conn: asyncpg.Connection) -> bool:
    """Check if schema_migrations table exists."""
    result = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'schema_migrations'
        )
    """)
    return result


async def apply_migration(
    conn: asyncpg.Connection,
    version: str,
    file_path: Path,
    dry_run: bool = False
) -> bool:
    """Apply a single migration."""
    logger.info(f"Processing migration {version}: {file_path.name}")
    
    # Read migration file
    content = file_path.read_text(encoding='utf-8')
    checksum = calculate_checksum(content)
    
    # Check if migration was already applied
    applied = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE version = $1)",
        version
    )
    
    if applied:
        # Check if checksum matches
        existing_checksum = await conn.fetchval(
            "SELECT checksum FROM schema_migrations WHERE version = $1",
            version
        )
        if existing_checksum == checksum:
            logger.info(f"  ✓ Migration {version} already applied (checksum matches)")
            return True
        else:
            logger.warning(
                f"  ⚠ Migration {version} was applied but checksum differs! "
                f"Existing: {existing_checksum[:16]}..., New: {checksum[:16]}..."
            )
            if not dry_run:
                response = input(
                    f"  Do you want to re-apply migration {version}? (yes/no): "
                )
                if response.lower() != 'yes':
                    logger.info(f"  Skipping migration {version}")
                    return False
    
    if dry_run:
        logger.info(f"  [DRY RUN] Would apply migration {version}")
        return True
    
    # Apply migration in a transaction
    start_time = time.time()
    try:
        async with conn.transaction():
            # Execute migration SQL
            await conn.execute(content)
            
            # Record migration (if record_migration function exists)
            try:
                await conn.execute(
                    """
                    SELECT record_migration($1, $2, $3, $4, $5)
                    """,
                    version,
                    file_path.stem,
                    f"Migration from {file_path.name}",
                    checksum,
                    int((time.time() - start_time) * 1000)
                )
            except asyncpg.UndefinedFunctionError:
                # Fallback: insert directly if function doesn't exist
                await conn.execute(
                    """
                    INSERT INTO schema_migrations (version, name, description, checksum, execution_time_ms)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (version) DO UPDATE
                    SET name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        checksum = EXCLUDED.checksum,
                        execution_time_ms = EXCLUDED.execution_time_ms
                    """,
                    version,
                    file_path.stem,
                    f"Migration from {file_path.name}",
                    checksum,
                    int((time.time() - start_time) * 1000)
                )
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"  ✓ Applied migration {version} in {elapsed_ms}ms")
        return True
        
    except Exception as e:
        logger.error(f"  ✗ Failed to apply migration {version}: {e}")
        raise


async def run_migrations(
    connection_string: str,
    dry_run: bool = False
) -> int:
    """Run all pending migrations."""
    conn = None
    try:
        # Connect to database
        logger.info("Connecting to database...")
        conn = await asyncpg.connect(connection_string)
        
        # Check if schema_migrations table exists
        if not await check_schema_migrations_table(conn):
            logger.warning(
                "schema_migrations table does not exist. "
                "You may need to run migrations/003_schema_versioning.sql first."
            )
            if not dry_run:
                response = input("Create schema_migrations table? (yes/no): ")
                if response.lower() == 'yes':
                    # Create schema_migrations table
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS schema_migrations (
                            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            version TEXT NOT NULL UNIQUE,
                            name TEXT NOT NULL,
                            description TEXT,
                            applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            checksum TEXT,
                            execution_time_ms INTEGER,
                            CONSTRAINT valid_version CHECK (version ~ '^[0-9]{3}$')
                        );
                        CREATE INDEX IF NOT EXISTS idx_schema_migrations_version 
                            ON schema_migrations(version);
                    """)
                    logger.info("Created schema_migrations table")
                else:
                    logger.error("Cannot proceed without schema_migrations table")
                    return 1
        
        # Get migration files
        migrations = get_migration_files()
        if not migrations:
            logger.warning("No migration files found")
            return 0
        
        logger.info(f"Found {len(migrations)} migration file(s)")
        
        # Get applied migrations
        applied = await get_applied_migrations(conn)
        logger.info(f"Found {len(applied)} already applied migration(s)")
        
        # Apply pending migrations
        applied_count = 0
        for version, file_path in migrations:
            if version in applied and not dry_run:
                # Check if we should skip
                continue
            
            try:
                success = await apply_migration(conn, version, file_path, dry_run)
                if success:
                    applied_count += 1
            except Exception as e:
                logger.error(f"Migration {version} failed: {e}")
                return 1
        
        if dry_run:
            logger.info(f"[DRY RUN] Would apply {applied_count} migration(s)")
        else:
            logger.info(f"Successfully applied {applied_count} migration(s)")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        return 1
    finally:
        if conn:
            await conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run database migrations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (check what would be applied)
  python scripts/run_migrations.py --dry-run
  
  # Apply migrations using environment variable
  NEON_CONNECTION_STRING="..." python scripts/run_migrations.py
  
  # Apply migrations with explicit connection string
  python scripts/run_migrations.py --connection-string "postgresql://..."
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be applied without actually applying"
    )
    parser.add_argument(
        "--connection-string",
        help="Database connection string (overrides NEON_CONNECTION_STRING env var)"
    )
    
    args = parser.parse_args()
    
    # Get connection string
    connection_string = args.connection_string or os.getenv("NEON_CONNECTION_STRING")
    if not connection_string:
        logger.error(
            "Connection string required. "
            "Set NEON_CONNECTION_STRING env var or use --connection-string"
        )
        return 1
    
    # Run migrations
    return asyncio.run(run_migrations(connection_string, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
