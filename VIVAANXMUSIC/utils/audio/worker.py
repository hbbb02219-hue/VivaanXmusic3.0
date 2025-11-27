"""
Background Audio Processing Worker - VivaanXMusic 3.0
Async queue-based task processing with concurrency limits
"""

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class AudioTask:
    """Represents a single audio processing task"""
    task_id: str
    user_id: int
    input_path: Path
    output_path: Path
    preset: str
    created_at: float = field(default_factory=time.time)
    status: str = "queued"  # queued, processing, completed, failed
    progress: float = 0.0  # 0-100
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    callback: Optional[Callable] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    def get_duration(self) -> float:
        """Get task processing duration in seconds"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        if self.start_time:
            return time.time() - self.start_time
        return 0.0


class AudioWorker:
    """Background worker for audio processing tasks"""
    
    def __init__(self, max_concurrent: int = 2):
        self.queue: asyncio.Queue = None
        self.semaphore = None
        self.tasks: Dict[str, AudioTask] = {}
        self.running = False
        self.worker_task = None
        self.max_concurrent = max_concurrent
        self.user_tasks: Dict[int, list] = {}  # Track per-user tasks
        
        logger.info(f"AudioWorker initialized (max {max_concurrent} concurrent)")
    
    async def start(self):
        """Start the worker"""
        if self.running:
            logger.warning("Worker already running")
            return
        
        self.running = True
        self.queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        
        logger.info(f"✅ Audio worker started (max {self.max_concurrent} concurrent)")
    
    async def stop(self):
        """Stop the worker and cleanup"""
        self.running = False
        
        # Cancel pending tasks
        pending = [
            t for t in self.tasks.values() 
            if t.status in ["queued", "processing"]
        ]
        for task in pending:
            task.status = "failed"
            task.error = "Worker stopped"
        
        logger.info("⛔ Audio worker stopped")
    
    async def enqueue(
        self,
        task_id: str,
        user_id: int,
        input_path: Path,
        output_path: Path,
        preset: str,
        callback: Optional[Callable] = None,
    ) -> bool:
        """
        Enqueue a new audio processing task
        Returns True if successful, False if queue full
        """
        try:
            if not self.running:
                logger.error("Worker not running")
                return False
            
            if self.queue.qsize() >= 50:
                logger.warning("⚠️ Task queue full (50 max)")
                return False
            
            task = AudioTask(
                task_id=task_id,
                user_id=user_id,
                input_path=input_path,
                output_path=output_path,
                preset=preset,
                callback=callback,
            )
            
            self.tasks[task_id] = task
            
            # Track per-user tasks
            if user_id not in self.user_tasks:
                self.user_tasks[user_id] = []
            self.user_tasks[user_id].append(task_id)
            
            await self.queue.put(task)
            
            logger.info(
                f"📥 Task enqueued: {task_id[:8]}... "
                f"(queue: {self.queue.qsize()}, user: {user_id})"
            )
            return True
        
        except Exception as e:
            logger.error(f"❌ Error enqueueing task: {e}")
            return False
    
    async def process_worker(self, engine):
        """
        Main worker loop for processing audio tasks
        Should be run with: asyncio.create_task(worker.process_worker(engine))
        """
        logger.info("🔄 Worker processing loop started")
        
        while self.running:
            try:
                # Get task with timeout
                try:
                    task = await asyncio.wait_for(self.queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    continue
                
                # Acquire semaphore (concurrency limit)
                async with self.semaphore:
                    task.status = "processing"
                    task.progress = 10.0
                    task.start_time = time.time()
                    
                    logger.info(
                        f"⚙️ Processing: {task.task_id[:8]}... "
                        f"(preset: {task.preset})"
                    )
                    
                    try:
                        # Process audio file
                        task.progress = 25.0
                        
                        success = engine.process_audio_file(
                            task.input_path,
                            task.output_path,
                            task.preset,
                            timeout=300,
                        )
                        
                        task.progress = 95.0
                        
                        if success and task.output_path.exists():
                            task.status = "completed"
                            task.progress = 100.0
                            task.end_time = time.time()
                            task.result = {
                                "output_size": task.output_path.stat().st_size,
                                "duration": task.get_duration(),
                            }
                            logger.info(
                                f"✅ Completed: {task.task_id[:8]}... "
                                f"({task.get_duration():.1f}s)"
                            )
                        else:
                            task.status = "failed"
                            task.error = "Processing failed or output not created"
                            task.end_time = time.time()
                            logger.error(f"❌ Processing failed: {task.task_id[:8]}...")
                    
                    except Exception as e:
                        task.status = "failed"
                        task.error = str(e)
                        task.end_time = time.time()
                        logger.error(f"❌ Task error: {task.task_id[:8]}...: {e}")
                    
                    finally:
                        # Execute callback if provided
                        if task.callback:
                            try:
                                if asyncio.iscoroutinefunction(task.callback):
                                    await task.callback(task)
                                else:
                                    task.callback(task)
                            except Exception as e:
                                logger.error(f"❌ Error in task callback: {e}")
                        
                        # Mark task done in queue
                        self.queue.task_done()
                        
                        # Cleanup input file
                        try:
                            if task.input_path.exists():
                                task.input_path.unlink()
                        except:
                            pass
            
            except Exception as e:
                logger.error(f"❌ Worker loop error: {e}")
                await asyncio.sleep(1)
        
        logger.info("🛑 Worker processing loop stopped")
    
    def get_task_status(self, task_id: str) -> Optional[AudioTask]:
        """Get task status by ID"""
        return self.tasks.get(task_id)
    
    def get_user_tasks(self, user_id: int) -> list:
        """Get all tasks for a specific user"""
        if user_id not in self.user_tasks:
            return []
        
        return [
            self.tasks[task_id] 
            for task_id in self.user_tasks[user_id]
            if task_id in self.tasks
        ]
    
    def get_user_active_tasks(self, user_id: int) -> int:
        """Get count of active tasks for user"""
        user_tasks = self.get_user_tasks(user_id)
        return len([t for t in user_tasks if t.status in ["queued", "processing"]])
    
    def get_active_tasks(self) -> int:
        """Get total count of active tasks (queued + processing)"""
        return len([
            t for t in self.tasks.values() 
            if t.status in ["queued", "processing"]
        ])
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get worker statistics"""
        total_tasks = len(self.tasks)
        active = len([t for t in self.tasks.values() if t.status in ["queued", "processing"]])
        completed = len([t for t in self.tasks.values() if t.status == "completed"])
        failed = len([t for t in self.tasks.values() if t.status == "failed"])
        
        # Calculate average processing time
        completed_tasks = [t for t in self.tasks.values() if t.status == "completed"]
        avg_time = 0.0
        if completed_tasks:
            avg_time = sum(t.get_duration() for t in completed_tasks) / len(completed_tasks)
        
        return {
            "queue_size": self.queue.qsize() if self.queue else 0,
            "active_tasks": active,
            "total_tasks": total_tasks,
            "completed": completed,
            "failed": failed,
            "max_concurrent": self.max_concurrent,
            "running": self.running,
            "avg_processing_time": round(avg_time, 1),
        }
    
    def cleanup_old_tasks(self, older_than_hours: int = 24) -> int:
        """Remove old completed/failed tasks"""
        cutoff_time = time.time() - (older_than_hours * 3600)
        removed = 0
        
        task_ids_to_remove = [
            task_id for task_id, task in self.tasks.items()
            if task.end_time and task.end_time < cutoff_time
        ]
        
        for task_id in task_ids_to_remove:
            task = self.tasks.pop(task_id, None)
            if task and task.user_id in self.user_tasks:
                self.user_tasks[task.user_id].remove(task_id)
            removed += 1
        
        if removed > 0:
            logger.info(f"🗑️ Cleaned up {removed} old tasks")
        
        return removed
    
    def get_recent_tasks(self, limit: int = 10) -> list:
        """Get most recent tasks"""
        tasks = list(self.tasks.values())
        tasks.sort(key=lambda x: x.created_at, reverse=True)
        return tasks[:limit]
