"""
SignalAtlas Request Metrics

Tracks HTTP request metrics for monitoring and observability.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional


@dataclass
class RequestMetric:
    """Metrics for a single request."""
    url: str
    source_name: str
    status_code: Optional[int]
    duration: float
    success: bool
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class AggregatedMetrics:
    """Aggregated metrics for a source or domain."""
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_duration: float = 0.0
    status_codes: Dict[int, int] = field(default_factory=dict)
    errors: Dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.success_count / self.total_requests

    @property
    def avg_duration(self) -> float:
        if self.success_count == 0:
            return 0.0
        return self.total_duration / self.success_count


class RequestMetrics:
    """
    Collects and aggregates HTTP request metrics.

    Thread-safe metrics collection for monitoring.
    """

    def __init__(self):
        self._lock = Lock()
        self._requests: List[RequestMetric] = []
        self._by_source: Dict[str, AggregatedMetrics] = defaultdict(AggregatedMetrics)
        self._by_domain: Dict[str, AggregatedMetrics] = defaultdict(AggregatedMetrics)
        self._by_status: Dict[int, int] = defaultdict(int)

    def record(self, metric: RequestMetric) -> None:
        """Record a request metric."""
        with self._lock:
            self._requests.append(metric)

            # Aggregate by source
            source_metrics = self._by_source[metric.source_name]
            source_metrics.total_requests += 1
            if metric.success:
                source_metrics.success_count += 1
                source_metrics.total_duration += metric.duration
            else:
                source_metrics.failure_count += 1
            if metric.status_code:
                source_metrics.status_codes[metric.status_code] += 1
            if metric.error:
                source_metrics.errors[metric.error] += 1

            # Aggregate by domain
            domain = self._extract_domain(metric.url)
            domain_metrics = self._by_domain[domain]
            domain_metrics.total_requests += 1
            if metric.success:
                domain_metrics.success_count += 1
                domain_metrics.total_duration += metric.duration
            else:
                domain_metrics.failure_count += 1
            if metric.status_code:
                domain_metrics.status_codes[metric.status_code] += 1

            # Aggregate by status
            if metric.status_code:
                self._by_status[metric.status_code] += 1

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or "unknown"

    def get_source_metrics(self, source_name: str) -> Optional[AggregatedMetrics]:
        """Get metrics for a specific source."""
        with self._lock:
            return self._by_source.get(source_name)

    def get_domain_metrics(self, domain: str) -> Optional[AggregatedMetrics]:
        """Get metrics for a specific domain."""
        with self._lock:
            return self._by_domain.get(domain)

    def get_status_distribution(self) -> Dict[int, int]:
        """Get distribution of status codes."""
        with self._lock:
            return dict(self._by_status)

    def get_summary(self) -> Dict[str, Any]:
        """Get overall metrics summary."""
        with self._lock:
            total = len(self._requests)
            success = sum(1 for r in self._requests if r.success)
            return {
                "total_requests": total,
                "success_count": success,
                "failure_count": total - success,
                "success_rate": success / total if total > 0 else 0.0,
                "sources": {k: v.to_dict() for k, v in self._by_source.items()},
                "domains": {k: v.to_dict() for k, v in self._by_domain.items()},
                "status_codes": dict(self._by_status),
            }

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._requests.clear()
            self._by_source.clear()
            self._by_domain.clear()
            self._by_status.clear()


# Global metrics instance
metrics = RequestMetrics()
