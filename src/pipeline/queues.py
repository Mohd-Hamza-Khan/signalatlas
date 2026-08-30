"""
SignalAtlas Pipeline Queues

In-memory queue management for Phase 1.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from structlog import get_logger

logger = get_logger(__name__)


class QueueType(Enum):
    """Types of queues in the pipeline."""
    CRAWL_STARTUP = "crawl:startup"
    CRAWL_PRODUCT = "crawl:product"
    CRAWL_PAPER = "crawl:paper"
    CRAWL_NEWS = "crawl:news"
    CRAWL_JOB = "crawl:job"
    EXTRACT = "extract"
    ENRICH_GITHUB = "enrich:github"
    RESOLVE_ENTITY = "resolve:entity"
    EXPORT_SHEETS = "export:sheets"
    DEADLETTER = "deadletter"


@dataclass
class QueueMessage:
    """Message to be processed from a queue."""
    job_id: UUID = field(default_factory=uuid4)
    url: Optional[str] = None
    source_name: Optional[str] = None
    document_id: Optional[UUID] = None
    data: Optional[Dict[str, Any]] = None
    attempt: int = 0
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    metadata: Dict[str, Any] = field(default_factory=dict)


class InMemoryQueue:
    """
    In-memory queue for Phase 1.

    Uses asyncio.Queue for simple in-memory message passing.
    Will be replaced with Redis in Phase 2.
    """

    def __init__(self, queue_type: QueueType):
        self.queue_type = queue_type
        self._queue: asyncio.Queue[QueueMessage] = asyncio.Queue()
        self._in_flight: Dict[UUID, QueueMessage] = {}
        self._completed: int = 0
        self._failed: int = 0
        self._lock = asyncio.Lock()

    async def enqueue(self, message: QueueMessage) -> None:
        """Add a message to the queue."""
        async with self._lock:
            await self._queue.put(message)
            logger.debug(
                "Message enqueued",
                queue=self.queue_type.value,
                job_id=str(message.job_id),
                url=message.url,
            )

    async def dequeue(self) -> Optional[QueueMessage]:
        """Get a message from the queue."""
        try:
            message = await self._queue.get()
            async with self._lock:
                self._in_flight[message.job_id] = message
            return message
        except asyncio.QueueEmpty:
            return None

    async def complete(self, message: QueueMessage) -> None:
        """Mark a message as completed."""
        async with self._lock:
            if message.job_id in self._in_flight:
                del self._in_flight[message.job_id]
                self._completed += 1
            self._queue.task_done()
            logger.debug(
                "Message completed",
                queue=self.queue_type.value,
                job_id=str(message.job_id),
            )

    async def fail(self, message: QueueMessage, error: Optional[str] = None) -> None:
        """Mark a message as failed."""
        async with self._lock:
            if message.job_id in self._in_flight:
                del self._in_flight[message.job_id]
                self._failed += 1
            self._queue.task_done()
            logger.warning(
                "Message failed",
                queue=self.queue_type.value,
                job_id=str(message.job_id),
                error=error,
            )

    async def requeue(self, message: QueueMessage) -> None:
        """Requeue a message (for retries)."""
        async with self._lock:
            if message.job_id in self._in_flight:
                del self._in_flight[message.job_id]
            message.attempt += 1
            await self._queue.put(message)
            logger.debug(
                "Message requeued",
                queue=self.queue_type.value,
                job_id=str(message.job_id),
                attempt=message.attempt,
            )

    def size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()

    def in_flight_count(self) -> int:
        """Get number of in-flight messages."""
        return len(self._in_flight)

    def stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            "queue_type": self.queue_type.value,
            "size": self.size(),
            "in_flight": self.in_flight_count(),
            "completed": self._completed,
            "failed": self._failed,
        }


# Global queue instances
queues: Dict[QueueType, InMemoryQueue] = {}


def get_queue(queue_type: QueueType) -> InMemoryQueue:
    """Get or create a queue instance."""
    if queue_type not in queues:
        queues[queue_type] = InMemoryQueue(queue_type)
    return queues[queue_type]


async def init_queues() -> None:
    """Initialize all queues."""
    for queue_type in QueueType:
        get_queue(queue_type)
    logger.info("In-memory queues initialized")
