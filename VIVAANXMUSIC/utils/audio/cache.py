"""
Caching layer for processed audio files - VivaanXMusic 3.0
Hash-based cache with TTL and automatic cleanup
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict
import asyncio
import aiofiles

from .config import (
    AUDIO_CACHE_DIR,
    CACHE_TTL,
    CACHE_ENABLED,
    MAX_CACHE_SIZE,
    CACHE_CHECK_INTERVAL,
)

logger = logging.getLogger(__name__)


class AudioCache:
    """Hash-based cache for processed audio files"""
    
    def __init__(self):
        self.cache_dir = AUDIO_CACHE_DIR
        self.enabled = CACHE_ENABLED
        self.ttl = CACHE_TTL
        self.max_size = MAX_CACHE_SIZE
        self.check_interval = CACHE_CHECK_INTERVAL
        self._last_cleanup = time.time()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"AudioCache initialized: {self.cache_dir}")
    
    @staticmethod
    def _compute_hash(file_data: bytes, preset_id: str) -> str:
        """Compute MD5 hash for cache key"""
        combined = file_data + preset_id.encode()
        return hashlib.md5(combined).hexdigest()
    
    def _get_cache_path(self, cache_hash: str, preset_id: str) -> Path:
        """Get full cache file path"""
        preset_dir = self.cache_dir / preset_id
        preset_dir.mkdir(parents=True, exist_ok=True)
        return preset_dir / f"{cache_hash}.mp3"
    
    def _get_metadata_path(self, cache_path: Path) -> Path:
        """Get metadata file path for cache entry"""
        return cache_path.parent / f"{cache_path.stem}.json"
    
    async def get(self, file_data: bytes, preset_id: str) -> Optional[Path]:
        """
        Retrieve cached file if exists and not expired.
        Returns Path if found, None otherwise.
        """
        if not self.enabled:
            return None
        
        try:
            cache_hash = self._compute_hash(file_data, preset_id)
            cache_path = self._get_cache_path(cache_hash, preset_id)
            metadata_path = self._get_metadata_path(cache_path)
            
            # Check if cache file exists
            if not cache_path.exists():
                logger.debug(f"Cache miss: {cache_hash[:8]}... ({preset_id})")
                return None
            
            # Check if metadata exists and not expired
            if not metadata_path.exists():
                logger.debug(f"Cache metadata missing: {cache_hash[:8]}...")
                return None
            
            async with aiofiles.open(metadata_path, "r") as f:
                content = await f.read()
                metadata = json.loads(content)
                
                created_at = metadata.get("created_at", 0)
                if time.time() - created_at > self.ttl:
                    logger.info(f"Cache expired: {cache_hash[:8]}... ({preset_id})")
                    await self.delete(cache_path)
                    return None
                
                logger.info(f"✅ Cache hit: {cache_hash[:8]}... ({preset_id})")
                return cache_path
        
        except Exception as e:
            logger.warning(f"Error reading cache: {e}")
            return None
    
    async def set(
        self,
        file_data: bytes,
        preset_id: str,
        output_path: Path,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Store processed audio in cache.
        Returns True if successful.
        """
        if not self.enabled:
            return False
        
        try:
            cache_hash = self._compute_hash(file_data, preset_id)
            cache_path = self._get_cache_path(cache_hash, preset_id)
            metadata_path = self._get_metadata_path(cache_path)
            
            # Copy output file to cache (or create symlink)
            if output_path.exists():
                try:
                    # Try symlink first (faster)
                    if cache_path.exists():
                        cache_path.unlink()
                    cache_path.symlink_to(output_path)
                except (OSError, FileExistsError):
                    # Fallback to copy
                    import shutil
                    shutil.copy2(output_path, cache_path)
            
            # Write metadata
            meta = metadata or {}
            meta.update({
                "hash": cache_hash,
                "preset": preset_id,
                "created_at": time.time(),
                "ttl": self.ttl,
                "file_size": output_path.stat().st_size if output_path.exists() else 0,
            })
            
            async with aiofiles.open(metadata_path, "w") as f:
                await f.write(json.dumps(meta, indent=2))
            
            logger.info(f"✅ Cached: {cache_hash[:8]}... ({preset_id}) - {meta['file_size'] / 1024:.1f}KB")
            
            # Check total cache size and cleanup if needed
            await self._cleanup_if_needed()
            
            return True
        
        except Exception as e:
            logger.error(f"Error caching file: {e}")
            return False
    
    async def delete(self, cache_path: Path) -> bool:
        """Delete cache entry and its metadata"""
        try:
            metadata_path = self._get_metadata_path(cache_path)
            
            if cache_path.exists():
                cache_path.unlink()
            if metadata_path.exists():
                metadata_path.unlink()
            
            logger.debug(f"Deleted cache: {cache_path.name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting cache: {e}")
            return False
    
    async def _cleanup_if_needed(self):
        """Cleanup expired cache entries if size exceeded or interval passed"""
        now = time.time()
        
        # Only cleanup every CHECK_INTERVAL seconds
        if now - self._last_cleanup < self.check_interval:
            return
        
        self._last_cleanup = now
        
        try:
            # Get all cache entries
            entries = []
            for preset_dir in self.cache_dir.iterdir():
                if preset_dir.is_dir():
                    for cache_file in preset_dir.glob("*.mp3"):
                        metadata_file = cache_file.parent / f"{cache_file.stem}.json"
                        if metadata_file.exists():
                            entries.append((cache_file, metadata_file))
            
            # Sort by creation time (oldest first)
            entries_with_time = []
            for cache_file, metadata_file in entries:
                try:
                    async with aiofiles.open(metadata_file, "r") as f:
                        content = await f.read()
                        meta = json.loads(content)
                        entries_with_time.append((cache_file, metadata_file, meta.get("created_at", 0)))
                except:
                    entries_with_time.append((cache_file, metadata_file, 0))
            
            entries_with_time.sort(key=lambda x: x[2])
            
            # Delete expired entries
            deleted = 0
            for cache_file, metadata_file, created_at in entries_with_time:
                if now - created_at > self.ttl:
                    await self.delete(cache_file)
                    deleted += 1
            
            # Delete oldest entries if total size exceeds max
            total_size = sum(
                f.stat().st_size for f in self.cache_dir.rglob("*.mp3") 
                if f.is_file()
            )
            
            if total_size > self.max_size:
                logger.info(f"Cache size {total_size / 1024 / 1024:.1f}MB exceeds limit, cleanup...")
                for cache_file, metadata_file, _ in entries_with_time[:-5]:  # Keep at least 5
                    await self.delete(cache_file)
                    deleted += 1
                    total_size = sum(
                        f.stat().st_size for f in self.cache_dir.rglob("*.mp3")
                        if f.is_file()
                    )
                    if total_size < self.max_size * 0.8:
                        break
            
            if deleted > 0:
                logger.info(f"🗑️ Cleanup: Removed {deleted} expired cache entries")
        
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def clear_all(self) -> int:
        """Clear entire cache"""
        count = 0
        try:
            for preset_dir in self.cache_dir.iterdir():
                if preset_dir.is_dir():
                    for cache_file in preset_dir.glob("*.mp3"):
                        await self.delete(cache_file)
                        count += 1
            logger.info(f"✅ Cleared cache: {count} entries")
            return count
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return count
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        total_size = 0
        total_files = 0
        
        try:
            for preset_dir in self.cache_dir.iterdir():
                if preset_dir.is_dir():
                    for cache_file in preset_dir.glob("*.mp3"):
                        total_size += cache_file.stat().st_size
                        total_files += 1
        except:
            pass
        
        return {
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "max_size_mb": round(self.max_size / (1024 * 1024), 2),
            "usage_percent": round((total_size / self.max_size) * 100, 1) if self.max_size > 0 else 0,
            "cache_enabled": self.enabled,
            "ttl_hours": self.ttl / 3600,
        }
