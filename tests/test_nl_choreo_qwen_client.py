import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

path = os.getcwd() + r'/src/pyfii'
sys.path.append(path)

from extensions.nl_choreo.inspector import _extract_text_from_response
from extensions.nl_choreo.qwen_client import (
    QwenConfig,
    QwenRetryableError,
    QwenVideoClient,
    RetryPolicy,
    TimeoutPolicy,
    extract_response_text,
)


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _qwen_config_from_test_json(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    retry = RetryPolicy(**payload.pop("retry", {}))
    timeout = TimeoutPolicy(**payload.pop("timeout", {}))
    return QwenConfig(**payload, retry=retry, timeout=timeout)


class TestNlChoreoQwenClient(unittest.TestCase):
    def test_default_config_has_empty_endpoint_fields(self):
        cfg = QwenConfig()
        self.assertEqual(cfg.base_url, "")
        self.assertEqual(cfg.api_key, "")
        self.assertEqual(cfg.upload_endpoint, "")

    def test_test_side_json_loader_builds_qwen_config(self):
        cfg = _qwen_config_from_test_json(Path(__file__).with_name("nl_choreo_qwen.example.json"))
        self.assertEqual(cfg.base_url, "https://ai.kevin0412.top/v1")
        self.assertEqual(cfg.api_key, "EMPTY")
        self.assertEqual(cfg.upload_endpoint, "https://ai.kevin0412.top/video-upload/v1/videos")
        self.assertEqual(cfg.retry.max_attempts, 2)
        self.assertEqual(cfg.timeout.inspect_sec, 2.0)

    @patch("extensions.nl_choreo.qwen_client.httpx.post")
    def test_upload_retry_then_success(self, mock_post):
        calls = [
            _FakeResponse(status_code=503, payload={}),
            _FakeResponse(status_code=200, payload={"url": "http://example/video.mp4"}),
        ]
        mock_post.side_effect = calls

        cfg = QwenConfig(
            upload_endpoint="http://example/upload",
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
        cfg = QwenConfig(upload_endpoint="http://example/upload", retry=RetryPolicy(max_attempts=2))
        client = QwenVideoClient(cfg)
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            with self.assertRaises(Exception):
                client.upload_video(f.name)

    def test_extract_response_text_prefers_content(self):
        resp = {
            "choices": [
                {
                    "message": {
                        "content": "final answer",
                        "reasoning_content": "hidden chain",
                    }
                }
            ]
        }
        self.assertEqual(extract_response_text(resp), "final answer")

    def test_extract_response_text_falls_back_to_reasoning_content(self):
        resp = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "reasoning_content": "fallback answer",
                    }
                }
            ]
        }
        self.assertEqual(extract_response_text(resp), "fallback answer")

    def test_inspector_extract_text_uses_reasoning_content_fallback(self):
        resp = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "reasoning_content": '{"issues":[],"suggest_regenerate":false}',
                    }
                }
            ]
        }
        self.assertEqual(_extract_text_from_response(resp), '{"issues":[],"suggest_regenerate":false}')


if __name__ == "__main__":
    unittest.main()
