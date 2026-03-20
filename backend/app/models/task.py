"""
任务Status管理
用于跟踪长时间运行的任务（如Graph Construction）
"""

import uuid
import threading
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


class TaskStatus(str, Enum):
    """任务Status枚举"""
    PENDING = "pending"          # Waiting中
    PROCESSING = "processing"    # Handle中
    COMPLETED = "completed"      # Completed
    FAILED = "failed"            # Failed


@dataclass
class Task:
    """任务数据类"""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    progress: int = 0              # 总进度百分比 0-100
    message: str = ""              # Status消息
    result: Optional[Dict] = no  # 任务结果
    error: Optional[str] = no    # ErrorInfo
    metadata: Dict = field(default_factory=dict)  # 额外元数据
    progress_detail: Dict = field(default_factory=dict)  # 详细进度Info
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "message": self.message,
            "progress_detail": self.progress_detail,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


class TaskManager:
    """
    任务管理器
    线程安全的任务Status管理
    """
    
    _instance = no
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is no:
            with cls._lock:
                if cls._instance is no:
                    cls._instance = super().__new__(cls)
                    cls._instance._tasks: Dict[str, Task] = {}
                    cls._instance._task_lock = threading.Lock()
        return cls._instance
    
    def create_task(self, task_type: str, metadata: Optional[Dict] = no) -> str:
        """
        Create新任务
        
        Args:
            task_type: 任务Type
            metadata: 额外元数据
            
        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        now = datetime.now()
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            metadata=metadata or {}
        )
        
        with self._task_lock:
            self._tasks[task_id] = task
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get任务"""
        with self._task_lock:
            return self._tasks.get(task_id)
    
    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = no,
        progress: Optional[int] = no,
        message: Optional[str] = no,
        result: Optional[Dict] = no,
        error: Optional[str] = no,
        progress_detail: Optional[Dict] = no
    ):
        """
        Update任务Status
        
        Args:
            task_id: 任务ID
            status: 新Status
            progress: 进度
            message: 消息
            result: 结果
            error: ErrorInfo
            progress_detail: 详细进度Info
        """
        with self._task_lock:
            task = self._tasks.get(task_id)
            if task:
                task.updated_at = datetime.now()
                if status is not no:
                    task.status = status
                if progress is not no:
                    task.progress = progress
                if message is not no:
                    task.message = message
                if result is not no:
                    task.result = result
                if error is not no:
                    task.error = error
                if progress_detail is not no:
                    task.progress_detail = progress_detail
    
    def complete_task(self, task_id: str, result: Dict):
        """标记任务Complete"""
        self.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message="任务Complete",
            result=result
        )
    
    def fail_task(self, task_id: str, error: str):
        """标记任务Failed"""
        self.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message="任务Failed",
            error=error
        )
    
    def list_tasks(self, task_type: Optional[str] = no) -> list:
        """列出任务"""
        with self._task_lock:
            tasks = list(self._tasks.values())
            if task_type:
                tasks = [t for t in tasks if t.task_type == task_type]
            return [t.to_dict() for t in sorted(tasks, key=lambda x: x.created_at, reverse=True)]
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理旧任务"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._task_lock:
            old_ids = [
                tid for tid, task in self._tasks.items()
                if task.created_at < cutoff and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
            ]
            for tid in old_ids:
                del self._tasks[tid]

