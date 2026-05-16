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
    AIProviderConfig,
    QwenConfig,
    QwenVideoClient,
    RetryPolicy,
    TimeoutPolicy,
    ai_provider_config_from_dict,
    extract_response_text,
)


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


AI_PROVIDERS_EXAMPLE = Path(__file__).resolve().parents[1] / "ai_providers.example.json"


def _ai_provider_config_from_json(path, provider=None):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ai_provider_config_from_dict(payload, provider=provider, environ={})


class TestNlChoreoQwenClient(unittest.TestCase):
    def test_default_config_has_empty_endpoint_fields(self):
        cfg = AIProviderConfig()
        self.assertEqual(cfg.base_url, "")
        self.assertEqual(cfg.api_key, "")
        self.assertEqual(cfg.upload_endpoint, "")

    def test_root_json_loader_builds_qwen_config(self):
        cfg = _ai_provider_config_from_json(AI_PROVIDERS_EXAMPLE)
        self.assertEqual(cfg.base_url, "")
        self.assertEqual(cfg.api_key, "")
        self.assertEqual(cfg.upload_endpoint, "")
        self.assertFalse(cfg.enable_thinking)
        self.assertEqual(cfg.retry.max_attempts, 2)
        self.assertEqual(cfg.timeout.inspect_sec, 2.0)

    def test_root_json_loader_selects_custom_gpt_config(self):
        cfg = _ai_provider_config_from_json(AI_PROVIDERS_EXAMPLE, "custom_gpt")
        self.assertEqual(cfg.base_url, "")
        self.assertEqual(cfg.api_key, "")
        self.assertEqual(cfg.model, "gpt-5.5")
        self.assertEqual(cfg.upload_endpoint, "")
        self.assertEqual(cfg.reasoning_effort, "xhigh")
        self.assertEqual(cfg.max_output_tokens, 98304)
        self.assertIsNone(cfg.enable_thinking)

    def test_root_json_loader_selects_deepseek_config(self):
        cfg = _ai_provider_config_from_json(AI_PROVIDERS_EXAMPLE, "deepseek")
        self.assertEqual(cfg.base_url, "https://api.deepseek.com")
        self.assertEqual(cfg.api_key, "")
        self.assertEqual(cfg.model, "deepseek-v4-flash")
        self.assertEqual(cfg.reasoning_effort, "max")
        self.assertEqual(cfg.extra_body, {"thinking": {"type": "enabled"}})
        self.assertIsNone(cfg.enable_thinking)

    def test_root_json_loader_selects_deepseek_pro_config(self):
        cfg = _ai_provider_config_from_json(AI_PROVIDERS_EXAMPLE, "deepseek_pro")
        self.assertEqual(cfg.base_url, "https://api.deepseek.com")
        self.assertEqual(cfg.api_key, "")
        self.assertEqual(cfg.model, "deepseek-v4-pro")
        self.assertEqual(cfg.reasoning_effort, "max")

    def test_provider_config_uses_matching_env_fallbacks(self):
        cfg = ai_provider_config_from_dict(
            {"provider": "custom_gpt", "providers": {"custom_gpt": {"model": "gpt-test"}}},
            environ={
                "PYFII_CUSTOM_GPT_BASE_URL": "https://gpt.example/v1",
                "PYFII_CUSTOM_GPT_API_KEY": "custom-key",
            },
        )
        self.assertEqual(cfg.base_url, "https://gpt.example/v1")
        self.assertEqual(cfg.api_key, "custom-key")
        self.assertEqual(cfg.model, "gpt-test")

    def test_completion_kwargs_carries_reasoning_and_provider_extra_body(self):
        cfg = AIProviderConfig(
            reasoning_effort="max",
            thinking={"type": "enabled"},
            extra_body={"provider_option": "enabled", "thinking": {"type": "disabled"}},
        )
        payload = QwenVideoClient(cfg)._completion_kwargs(
            model="test-model",
            temperature=0.7,
            top_p=0.9,
            extra_body={"top_k": 20},
        )
        self.assertEqual(payload["reasoning_effort"], "max")
        self.assertNotIn("temperature", payload)
        self.assertNotIn("top_p", payload)
        self.assertEqual(payload["extra_body"]["provider_option"], "enabled")
        self.assertEqual(payload["extra_body"]["top_k"], 20)
        self.assertEqual(payload["extra_body"]["thinking"], {"type": "enabled"})

    def test_completion_kwargs_carries_qwen_enable_thinking(self):
        cfg = AIProviderConfig(enable_thinking=True)
        payload = QwenVideoClient(cfg)._completion_kwargs(model="test-model")
        self.assertTrue(payload["extra_body"]["chat_template_kwargs"]["enable_thinking"])

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
