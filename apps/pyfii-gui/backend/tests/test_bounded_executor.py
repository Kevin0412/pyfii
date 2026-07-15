from threading import Event
import unittest

from pyfii_gui_api.services.bounded_executor import BoundedExecutor, ExecutorBusy


class BoundedExecutorTests(unittest.TestCase):
    def test_rejects_work_after_workers_and_queue_are_full(self):
        started = Event()
        release = Event()
        executor = BoundedExecutor(
            max_workers=1,
            max_queue_size=1,
            thread_name_prefix="bounded-test",
        )

        def blocking_work():
            started.set()
            release.wait(timeout=2)

        try:
            first = executor.submit(blocking_work)
            self.assertTrue(started.wait(timeout=1))
            second = executor.submit(lambda: "queued")

            with self.assertRaises(ExecutorBusy):
                executor.submit(lambda: "rejected")

            release.set()
            first.result(timeout=1)
            self.assertEqual(second.result(timeout=1), "queued")
            self.assertEqual(executor.submit(lambda: "accepted").result(timeout=1), "accepted")
        finally:
            release.set()
            executor.shutdown()

    def test_rejects_invalid_capacity(self):
        with self.assertRaises(ValueError):
            BoundedExecutor(
                max_workers=0,
                max_queue_size=0,
                thread_name_prefix="invalid-test",
            )
        with self.assertRaises(ValueError):
            BoundedExecutor(
                max_workers=1,
                max_queue_size=-1,
                thread_name_prefix="invalid-test",
            )


if __name__ == "__main__":
    unittest.main()
