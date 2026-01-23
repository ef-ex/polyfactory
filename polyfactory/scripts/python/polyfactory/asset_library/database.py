"""
SQLite database management for asset library
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class AssetDatabase:
    """Manages the asset library SQLite database"""
    
    def __init__(self, db_path: str = None, debug: bool = False):
        """Initialize database connection
        
        Args:
            db_path: Path to SQLite database. If None, uses PF_ASSET_DB env var
            debug: Enable debug print statements
        """
        if db_path is None:
            db_path = os.environ.get('PF_ASSET_DB', '')
            if not db_path:
                raise ValueError("Database path not specified and PF_ASSET_DB environment variable not set")
        
        self.db_path = db_path
        self.debug = debug
        self._ensure_directory()
        self.conn = None
        self.cursor = None
        self._connect()
        self._initialize_schema()
    
    def _ensure_directory(self):
        """Create database directory if it doesn't exist"""
        # Resolve the full path first
        self.db_path = os.path.abspath(self.db_path)
        db_dir = os.path.dirname(self.db_path)
        
        if not db_dir:
            # If no directory specified, use current directory
            self.db_path = os.path.join(os.getcwd(), os.path.basename(self.db_path))
            db_dir = os.path.dirname(self.db_path)
        
        # Create directory structure
        try:
            os.makedirs(db_dir, exist_ok=True)
            if self.debug:
                print(f"Database directory ensured: {db_dir}")
        except Exception as e:
            raise IOError(f"Cannot create database directory {db_dir}: {e}")
        
        # Verify directory is writable by trying to create a test file
        test_file = os.path.join(db_dir, '.test_write')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            if self.debug:
                print(f"Directory is writable: {db_dir}")
        except Exception as e:
            raise IOError(f"Directory is not writable {db_dir}: {e}")
    
    def _connect(self):
        """Establish database connection"""
        if self.debug:
            print(f"Connecting to database: {self.db_path}")
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Allow access by column name
            self.cursor = self.conn.cursor()
            if self.debug:
                print(f"Database connection successful")
        except Exception as e:
            raise IOError(f"Cannot connect to database {self.db_path}: {e}")
    
    def _initialize_schema(self):
        """Create database tables if they don't exist"""
        # Assets table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                thumbnail_static TEXT,
                thumbnail_turntable TEXT,
                turntable_frames INTEGER DEFAULT 36,
                poly_count INTEGER,
                bbox_min_x REAL,
                bbox_min_y REAL,
                bbox_min_z REAL,
                bbox_max_x REAL,
                bbox_max_y REAL,
                bbox_max_z REAL,
                notes TEXT,
                date_created TEXT NOT NULL,
                date_modified TEXT NOT NULL
            )
        """)
        
        # Tags table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT NOT NULL UNIQUE
            )
        """)
        
        # Asset-Tags junction table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS asset_tags (
                asset_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (asset_id, tag_id),
                FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for better query performance
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_assets_name ON assets(name)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(tag_name)
        """)
        
        self.conn.commit()
    
    def add_asset(self, name: str, category: str, file_path: str, 
                  thumbnail_static: str = None, thumbnail_turntable: str = None,
                  poly_count: int = None, bbox_min: Tuple[float, float, float] = None,
                  bbox_max: Tuple[float, float, float] = None, notes: str = None,
                  tags: List[str] = None) -> int:
        """Add a new asset to the database
        
        Args:
            name: Asset name
            category: Asset category
            file_path: Path to the asset file
            thumbnail_static: Path to static thumbnail
            thumbnail_turntable: Path to turntable folder or sprite sheet
            poly_count: Number of polygons
            bbox_min: Bounding box minimum (x, y, z)
            bbox_max: Bounding box maximum (x, y, z)
            notes: Optional notes
            tags: List of tag strings
            
        Returns:
            Asset ID
        """
        now = datetime.now().isoformat()
        
        bbox_min = bbox_min or (None, None, None)
        bbox_max = bbox_max or (None, None, None)
        
        self.cursor.execute("""
            INSERT INTO assets (
                name, category, file_path, thumbnail_static, thumbnail_turntable,
                poly_count, bbox_min_x, bbox_min_y, bbox_min_z,
                bbox_max_x, bbox_max_y, bbox_max_z, notes,
                date_created, date_modified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, category, file_path, thumbnail_static, thumbnail_turntable,
              poly_count, bbox_min[0], bbox_min[1], bbox_min[2],
              bbox_max[0], bbox_max[1], bbox_max[2], notes, now, now))
        
        asset_id = self.cursor.lastrowid
        
        # Add tags
        if tags:
            self._add_tags_to_asset(asset_id, tags)
        
        self.conn.commit()
        return asset_id
    
    def _add_tags_to_asset(self, asset_id: int, tags: List[str]):
        """Associate tags with an asset"""
        for tag in tags:
            tag = tag.strip().lower()
            if not tag:
                continue
            
            # Insert tag if it doesn't exist
            self.cursor.execute("""
                INSERT OR IGNORE INTO tags (tag_name) VALUES (?)
            """, (tag,))
            
            # Get tag ID
            self.cursor.execute("""
                SELECT id FROM tags WHERE tag_name = ?
            """, (tag,))
            tag_id = self.cursor.fetchone()[0]
            
            # Link asset and tag
            self.cursor.execute("""
                INSERT OR IGNORE INTO asset_tags (asset_id, tag_id) VALUES (?, ?)
            """, (asset_id, tag_id))
    
    def get_asset(self, asset_id: int) -> Optional[Dict]:
        """Get asset by ID
        
        Args:
            asset_id: Asset ID
            
        Returns:
            Asset data as dictionary or None if not found
        """
        self.cursor.execute("""
            SELECT * FROM assets WHERE id = ?
        """, (asset_id,))
        
        row = self.cursor.fetchone()
        if not row:
            return None
        
        asset = dict(row)
        asset['tags'] = self.get_asset_tags(asset_id)
        return asset
    
    def get_asset_tags(self, asset_id: int) -> List[str]:
        """Get all tags for an asset
        
        Args:
            asset_id: Asset ID
            
        Returns:
            List of tag strings
        """
        self.cursor.execute("""
            SELECT t.tag_name FROM tags t
            JOIN asset_tags at ON t.id = at.tag_id
            WHERE at.asset_id = ?
        """, (asset_id,))
        
        return [row[0] for row in self.cursor.fetchall()]
    
    def search_assets(self, search_term: str = None, category: str = None,
                     tags: List[str] = None, tag_mode: str = 'OR') -> List[Dict]:
        """Search assets with various filters
        
        Args:
            search_term: Search in name and notes
            category: Filter by category
            tags: Filter by tags
            tag_mode: 'OR' (any tag) or 'AND' (all tags)
            
        Returns:
            List of asset dictionaries
        """
        query = "SELECT DISTINCT a.* FROM assets a"
        conditions = []
        params = []
        
        # Join with tags if needed
        if tags:
            query += """
                JOIN asset_tags at ON a.id = at.asset_id
                JOIN tags t ON at.tag_id = t.id
            """
        
        # Build WHERE conditions
        if search_term:
            conditions.append("(a.name LIKE ? OR a.notes LIKE ?)")
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern, search_pattern])
        
        if category:
            conditions.append("a.category = ?")
            params.append(category)
        
        if tags:
            tag_placeholders = ','.join(['?'] * len(tags))
            conditions.append(f"t.tag_name IN ({tag_placeholders})")
            params.extend(tags)
        
        # Combine conditions
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        # For AND mode with tags, group and count
        if tags and tag_mode == 'AND':
            query += f" GROUP BY a.id HAVING COUNT(DISTINCT t.tag_name) = {len(tags)}"
        
        query += " ORDER BY a.name"
        
        self.cursor.execute(query, params)
        
        results = []
        for row in self.cursor.fetchall():
            asset = dict(row)
            asset['tags'] = self.get_asset_tags(asset['id'])
            results.append(asset)
        
        return results
    
    def get_all_categories(self) -> List[str]:
        """Get all unique categories
        
        Returns:
            List of category strings
        """
        self.cursor.execute("""
            SELECT DISTINCT category FROM assets ORDER BY category
        """)
        return [row[0] for row in self.cursor.fetchall()]
    
    def get_all_tags(self) -> List[str]:
        """Get all unique tags
        
        Returns:
            List of tag strings
        """
        self.cursor.execute("""
            SELECT tag_name FROM tags ORDER BY tag_name
        """)
        return [row[0] for row in self.cursor.fetchall()]
    
    def update_asset(self, asset_id: int, **kwargs):
        """Update asset fields
        
        Args:
            asset_id: Asset ID
            **kwargs: Fields to update (name, category, notes, etc.)
        """
        allowed_fields = {
            'name', 'category', 'file_path', 'thumbnail_static', 'thumbnail_turntable',
            'poly_count', 'bbox_min_x', 'bbox_min_y', 'bbox_min_z',
            'bbox_max_x', 'bbox_max_y', 'bbox_max_z', 'notes'
        }
        
        # Filter kwargs to allowed fields
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return
        
        # Add modification timestamp
        updates['date_modified'] = datetime.now().isoformat()
        
        # Build UPDATE query
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values())
        values.append(asset_id)
        
        self.cursor.execute(f"""
            UPDATE assets SET {set_clause} WHERE id = ?
        """, values)
        
        self.conn.commit()
    
    def delete_asset(self, asset_id: int):
        """Delete an asset from the database
        
        Args:
            asset_id: Asset ID
        """
        self.cursor.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        self.conn.commit()
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
