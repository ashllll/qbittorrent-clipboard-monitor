"""
通用弹性组件

提供速率限制、断路器、LRU缓存与性能统计，供客户端与AI分类器复用。
"""

import time
import threading
from collections import deque, OrderedDict
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, Dict, Deque


class RateLimiter:
    """简单的固定窗口速率限制器（默认按分钟）"""

    def __init__(self, max_requests_per_minute: int, window_seconds: int = 60):
        self.max_requests = max(1, max_requests_per_minute)
        self.window_seconds = max(1, window_seconds)
        self._lock = threading.Lock()
        self._requests: Deque[float] = deque()

    def allow(self) -> bool:
        """返回是否允许当前请求"""
        now = time.time()
        with self._lock:
            while self._requests and now - self._requests[0] > self.window_seconds:
                self._requests.popleft()

            if len(self._requests) >= self.max_requests:
                return False

            self._requests.append(now)
            return True


@dataclass
class CircuitBreakerState:
    state: str = "closed"  # closed, open, half_open
    failure_count: int = 0
    last_failure_time: Optional[float] = None
    opened_at: Optional[float] = None


class CircuitBreaker:
    """通用断路器实现"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        on_state_change: Optional[Callable[[str], None]] = None,
    ):
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_timeout = max(0.1, recovery_timeout)
        self._state = CircuitBreakerState()
        self._lock = threading.Lock()
        self._callback = on_state_change

    def _set_state(self, state: str):
        if self._state.state != state:
            self._state.state = state
            if self._callback:
                self._callback(state)

    def allow(self) -> bool:
        """是否允许请求通过"""
        with self._lock:
            if self._state.state == "open":
                if (
                    self._state.opened_at
                    and time.time() - self._state.opened_at > self.recovery_timeout
                ):
                    self._set_state("half_open")
                    return True
                return False
            return True

    def record_success(self):
        with self._lock:
            if self._state.state in ("half_open", "open"):
                self._set_state("closed")
                self._state.failure_count = 0
                self._state.opened_at = None
            else:
                self._state.failure_count = max(0, self._state.failure_count - 1)

    def record_failure(self):
        with self._lock:
            self._state.failure_count += 1
            self._state.last_failure_time = time.time()
            if self._state.failure_count >= self.failure_threshold:
                self._set_state("open")
                self._state.opened_at = time.time()

    @property
    def state(self) -> str:
        return self._state.state

    @property
    def failure_count(self) -> int:
        return self._state.failure_count


class LRUCache:
    """线程安全的LRU缓存"""

    def __init__(self, max_size: int = 1024, ttl_seconds: Optional[int] = None):
        self.max_size = max(1, max_size)
        self.ttl = ttl_seconds
        self._entries: "OrderedDict[str, tuple[Any, float]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._entries.get(key)
            if not item:
                return None
            value, timestamp = item
            if self.ttl and time.time() - timestamp > self.ttl:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return value

    def set(self, key: str, value: Any):
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
            self._entries[key] = (value, time.time())
            if len(self._entries) > self.max_size:
                self._entries.popitem(last=False)

    def clear(self):
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


@dataclass
class Metrics:
    requests: int = 0
    errors: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    response_times: list[float] = field(default_factory=list)
    last_request_time: Optional[str] = None

    def record_response_time(self, value: float, limit: int = 1000):
        self.response_times.append(value)
        if len(self.response_times) > limit:
            self.response_times[:] = self.response_times[-limit:]


class MetricsTracker:
    """线程安全的指标采集器"""

    def __init__(self):
        self._metrics = Metrics()
        self._lock = threading.Lock()

    def inc(self, attr: str, value: int = 1):
        with self._lock:
            current = getattr(self._metrics, attr, 0)
            setattr(self._metrics, attr, current + value)

    def record_response(self, response_time: float):
        with self._lock:
            self._metrics.record_response_time(response_time)

    def update_last_request_time(self, iso_time: str):
        with self._lock:
            self._metrics.last_request_time = iso_time

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            metrics = self._metrics
            response_times = metrics.response_times[:]
        avg = sum(response_times) / len(response_times) if response_times else 0.0
        return {
            "requests": metrics.requests,
            "errors": metrics.errors,
            "cache_hits": metrics.cache_hits,
            "cache_misses": metrics.cache_misses,
            "avg_response_time": avg,
            "max_response_time": max(response_times) if response_times else 0.0,
            "min_response_time": min(response_times) if response_times else 0.0,
            "last_request_time": metrics.last_request_time,
        }
