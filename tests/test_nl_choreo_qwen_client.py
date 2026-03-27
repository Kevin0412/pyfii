import os
import sys
import tempfile
import unittest
from unittest.mock import patch

path = os.getcwd() + r'/src/pyfii'
sys.path.append(path)

from extensions.nl_choreo.qwen_client import (
    QwenConfig,
    QwenRetryableError,
    QwenVideoClient,
    RetryPolicy,
    TimeoutPolicy,
)


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class TestNlChoreoQwenClient(unittest.TestCase):
    @patch("extensions.nl_choreo.qwen_client.httpx.post")
    def test_upload_retry_then_success(self, mock_post):
        calls = [
            _FakeResponse(status_code=503, payload={}),
            _FakeResponse(status_code=200, payload={"url": "http://example/video.mp4"}),
        ]
        mock_post.side_effect = calls

        cfg = QwenConfig(
            retry=RetryPolicy(max_attempts=3, backoff_base_sec=0.01, backoff_factor=1.0, backoff_max_sec=0.02),
            timeout=TimeoutPolicy(upload_sec=2.0, inspect_sec=2.0),
        )
        client = QwenVideoClient(cfg)

        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            url = client.upload_video(f.name)
        self.assertIn("video.mp4", url)
        self.assertEqual(mock_post.call_count, 2)

    @patch("extensions.nl_choreo.qwen_client.httpx.post")
    def test_upload_non_retryable(self, mock_post):
        mock_post.return_value = _FakeResponse(status_code=401, payload={}, text="unauthorized")
        cfg = QwenConfig(retry=RetryPolicy(max_attempts=2))
        client = QwenVideoClient(cfg)
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            with self.assertRaises(Exception):
                client.upload_video(f.name)


if __name__ == "__main__":
    unittest.main()
