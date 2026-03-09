"""
In-application resource monitoring and metrics collection.
Provides real-time CPU and memory tracking for optimization insights.
"""

import os
import psutil
import time
from datetime import datetime
from typing import Optional


class ResourceMonitor:
    """Monitor application resource usage."""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.start_time = time.time()
        self.metrics = {
            "startup_memory_mb": self.get_memory_mb(),
            "startup_time": datetime.now().isoformat(),
        }

    def get_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024

    def get_cpu_percent(self) -> float:
        """Get CPU usage percentage (0-100)."""
        return self.process.cpu_percent(interval=0.1)

    def get_uptime_seconds(self) -> float:
        """Get application uptime in seconds."""
        return time.time() - self.start_time

    def get_connection_count(self) -> int:
        """Get number of open connections."""
        return len(self.process.connections(kind="inet"))

    def snapshot(self) -> dict:
        """Get current resource snapshot."""
        return {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": int(self.get_uptime_seconds()),
            "memory_mb": round(self.get_memory_mb(), 2),
            "cpu_percent": round(self.get_cpu_percent(), 2),
            "connections": self.get_connection_count(),
        }

    def check_constraints(self) -> Optional[str]:
        """Check if resources are constrained. Returns warning message or None."""
        memory_mb = self.get_memory_mb()

        # Warn if using >80% of 512MB
        if memory_mb > 400:
            return f"⚠️  Memory critical: {memory_mb:.0f}MB / 512MB allocated (80%+)"

        # Warn if using >70% of 512MB
        if memory_mb > 350:
            return f"⚠️  Memory high: {memory_mb:.0f}MB / 512MB allocated (70%+)"

        return None


# Global monitor instance
_monitor: Optional[ResourceMonitor] = None


def get_monitor() -> ResourceMonitor:
    """Get or create the global monitor."""
    global _monitor
    if _monitor is None:
        _monitor = ResourceMonitor()
    return _monitor


def log_startup_info():
    """Log startup resource information."""
    monitor = get_monitor()
    print(f"\n=== Application Startup ===")
    print(f"Memory: {monitor.metrics['startup_memory_mb']:.1f} MB")
    print(f"Allocated: 512 MB (Fargate 256 CPU + 512 MB)")
    print(f"Available: {512 - monitor.metrics['startup_memory_mb']:.1f} MB for processing")
    print(f"============================\n")


def log_resource_snapshot(label: str = ""):
    """Log current resource snapshot."""
    monitor = get_monitor()
    snapshot = monitor.snapshot()
    constraint_warning = monitor.check_constraints()

    prefix = f"[{label}] " if label else ""
    print(f"{prefix}Resources - Mem: {snapshot['memory_mb']}MB, CPU: {snapshot['cpu_percent']}%, Conn: {snapshot['connections']}")

    if constraint_warning:
        print(f"  {constraint_warning}")

    return snapshot
