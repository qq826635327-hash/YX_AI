"""Core logic unit tests.

Tests cover encrypt/decrypt roundtrip, secret masking, JSON extraction
from LLM responses, rule-based shot splitting, and role mapping.
"""

import json

import pytest

from app.core.config import encrypt_secret, decrypt_secret, mask_secret
from app.pipelines._llm_utils import _extract_json
from app.pipelines._extraction_stages import _rule_based_shots, _map_role


# ============================================================
# TC-UNIT-001: encrypt / decrypt roundtrip
# ============================================================

@pytest.mark.unit
def test_encrypt_decrypt_roundtrip():
    """Encrypt then decrypt should return the original plaintext."""
    plain = "sk-test-1234567890abcdef"
    encrypted = encrypt_secret(plain)
    assert encrypted != plain
    decrypted = decrypt_secret(encrypted)
    assert decrypted == plain


# ============================================================
# TC-UNIT-002: mask_secret
# ============================================================

@pytest.mark.unit
def test_mask_secret():
    """mask_secret should mask secrets based on length rules."""
    # Empty string returns empty
    assert mask_secret("") == ""
    # Short string (<=8 chars) fully masked
    assert mask_secret("short") == "*****"
    # Long string (>8 chars) shows first 4 and last 4
    assert mask_secret("abcdefghijklmnop") == "abcd****mnop"


# ============================================================
# TC-UNIT-003: _extract_json various formats
# ============================================================

@pytest.mark.unit
def test_extract_json_various_formats():
    """_extract_json should handle pure JSON, markdown-wrapped, arrays, and truncated JSON."""
    # Pure JSON object
    assert _extract_json('{"a": 1}') == {"a": 1}

    # Markdown code block wrapped
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    # JSON array
    assert _extract_json('[1, 2, 3]') == [1, 2, 3]

    # Truncated JSON array (missing closing ] but last object has its })
    result = _extract_json('[{"name": "a"}, {"name": "b"}')
    assert len(result) == 2

    # Invalid JSON should raise
    with pytest.raises(json.JSONDecodeError):
        _extract_json("not json at all")


# ============================================================
# TC-UNIT-004: _rule_based_shots
# ============================================================

@pytest.mark.unit
def test_rule_based_shots():
    """_rule_based_shots should split text by shot markers or return single shot."""
    # Text with shot markers
    text = "分镜1 描述A\n\n分镜2 描述B\n\n分镜3 描述C"
    shots = _rule_based_shots(text)
    assert len(shots) == 3
    assert shots[0]["shot_no"] == 1
    assert shots[2]["shot_no"] == 3

    # Empty text
    assert _rule_based_shots("") == []
    assert _rule_based_shots("   ") == []

    # Plain text without markers -> single shot
    text2 = "一段没有分镜标记的文本"
    shots2 = _rule_based_shots(text2)
    assert len(shots2) == 1


# ============================================================
# TC-UNIT-005: _map_role
# ============================================================

@pytest.mark.unit
def test_map_role():
    """_map_role should map Chinese/English role names to standard char_type."""
    assert _map_role("主角") == "protagonist"
    assert _map_role("配角") == "supporting"
    assert _map_role("群演") == "extra"
    assert _map_role("protagonist") == "protagonist"
    # Unknown roles default to "supporting"
    assert _map_role("unknown") == "supporting"
