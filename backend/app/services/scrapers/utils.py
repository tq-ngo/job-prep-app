import hashlib
from typing import Optional
from redis import Redis
import os

class DedupService:
    def __init__(self, redis_client: Optional[Redis] = None):
        if redis_client:
            self.redis = redis_client
        else:
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
            self.redis = Redis.from_url(redis_url, decode_responses=True)
        
        self.key_prefix = "scrape:dedup:v1:"
        self.ttl = 7 * 24 * 60 * 60  # 7 days
        self._local_cache = set()

    def _get_key(self, url: str, user_id: str) -> str:
        # Normalize and hash the URL to keep keys short and consistent
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        return f"{self.key_prefix}{user_id}:{url_hash}"

    def is_recently_seen(self, url: str, user_id: str) -> bool:
        """Checks if the URL was recently processed for this user."""
        key = self._get_key(url, user_id)
        
        # L1: Local cache check (Fastest)
        if key in self._local_cache:
            return True
            
        # L2: Redis check
        if self.redis.exists(key) > 0:
            self._local_cache.add(key)
            return True
            
        return False

    def mark_as_seen(self, url: str, user_id: str):
        """Marks the URL as seen with a 7-day TTL."""
        key = self._get_key(url, user_id)
        # Populate L1 and L2
        self._local_cache.add(key)
        self.redis.set(key, "1", ex=self.ttl)

class ScraperCircuitBreaker:
    def __init__(self, service_name: str, redis_client: Optional[Redis] = None):
        if redis_client:
            self.redis = redis_client
        else:
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
            self.redis = Redis.from_url(redis_url, decode_responses=True)
        
        self.service_name = service_name
        self.key_prefix = f"scrape:cb:v1:{service_name}:"
        self.threshold = 5  # Points before opening circuit
        self.open_duration = 30 * 60  # 30 minutes in seconds

    def _get_failures_key(self) -> str:
        return f"{self.key_prefix}failures"

    def _get_open_until_key(self) -> str:
        return f"{self.key_prefix}open_until"

    def is_open(self) -> bool:
        """Checks if the circuit is currently open."""
        open_until = self.redis.get(self._get_open_until_key())
        if not open_until:
            return False
        
        import time
        if float(open_until) > time.time():
            return True
        
        # Circuit duration expired
        return False

    def record_failure(self, points: int = 1):
        """Records a failure. If threshold is reached, opens the circuit."""
        failures = self.redis.incrby(self._get_failures_key(), points)
        if failures >= self.threshold:
            import time
            open_until = time.time() + self.open_duration
            self.redis.set(self._get_open_until_key(), str(open_until))
            # Reset failures once opened
            self.redis.set(self._get_failures_key(), "0")

    def record_success(self):
        """Records a success, resetting failure count."""
        self.redis.set(self._get_failures_key(), "0")
