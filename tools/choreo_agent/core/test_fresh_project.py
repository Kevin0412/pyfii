"""Fresh project test: bad code NEVER touches design.py."""

import sys, json, shutil, hashlib, tempfile, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_fresh_project_bad_code():
    """Init fresh project, mock bad LLM response, verify design.py UNCHANGED."""
    from unittest.mock import patch
    from core import Session
    from core.llm_client import LlmResponse

    # Create temp project
    tmp = Path(tempfile.mkdtemp())
    tmpl = Path(__file__).resolve().parent.parent / "project_template"
    shutil.copytree(tmpl, tmp, dirs_exist_ok=True)

    design_path = tmp / "scripts" / "design.py"
    before_hash = hashlib.sha256(design_path.read_bytes()).hexdigest()
    before_content = design_path.read_text()

    # Bad LLM response
    bad_text = "import math\ndrone.VelXY(120, 200)\ndrone.move2(100, 120, 150)"
    bad_resp = LlmResponse(text=bad_text, model="mock", input_tokens=5, output_tokens=15)

    # Mock config and chat
    with patch('core.session._load_provider_config',
               return_value={'supports_prefix_completion': False}):
        with patch('core.session.chat', return_value=bad_resp):
            try:
                s = Session(str(tmp))
                rounds = s.generate_until_safe_with_llm(
                    provider="mock", max_attempts=1
                )
            except Exception:
                pass

    # Verify unchanged
    after_hash = hashlib.sha256(design_path.read_bytes()).hexdigest()
    after_content = design_path.read_text()

    assert before_hash == after_hash, f"design.py hash changed (before={before_hash[:8]}, after={after_hash[:8]})"
    assert after_content == before_content, "design.py content changed"

    shutil.rmtree(tmp)
    print("PASSED: fresh project — bad code never touches design.py")


if __name__ == "__main__":
    test_fresh_project_bad_code()
    print("OK")
