from concurrent.futures import Future, ThreadPoolExecutor
from threading import BoundedSemaphore
from typing import Any, Callable


class ExecutorBusy(RuntimeError):
    """Raised when every worker and configured queue slot is occupied."""


class BoundedExecutor:
    """A thread pool with a fixed number of running and waiting tasks."""

    def __init__(
        self,
        *,
        max_workers: int,
        max_queue_size: int,
        thread_name_prefix: str,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1.")
        if max_queue_size < 0:
            raise ValueError("max_queue_size cannot be negative.")
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self._slots = BoundedSemaphore(max_workers + max_queue_size)
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        )

    def submit(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
        if not self._slots.acquire(blocking=False):
            raise ExecutorBusy("Executor capacity is full.")
        try:
            future = self._executor.submit(function, *args, **kwargs)
        except BaseException:
            self._slots.release()
            raise
        future.add_done_callback(lambda _future: self._slots.release())
        return future

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)
