"""Serialization utility tests.

Tests cover the serialize_model and serialize_models functions from
app.core.serialization, ensuring correct handling of datetime fields,
model lists, and None values.
"""

from datetime import datetime, timezone

import pytest
from sqlmodel import Field, SQLModel

from app.core.serialization import serialize_model, serialize_models


class _FakeModel(SQLModel):
    """Minimal SQLModel for testing serialization (not a table)."""

    id: str = "test-id-001"
    name: str = "测试"
    created_at: datetime = Field(default_factory=lambda: datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime(2026, 6, 20, 14, 0, 0, tzinfo=timezone.utc))


class _NaiveDatetimeModel(SQLModel):
    """Model with naive (timezone-unaware) datetime for testing."""

    id: str = "test-id-002"
    created_at: datetime = Field(default_factory=lambda: datetime(2026, 3, 10, 8, 0, 0))
    updated_at: datetime = Field(default_factory=lambda: datetime(2026, 3, 10, 9, 0, 0))


@pytest.mark.unit
class TestSerializeModel:
    """Unit tests for serialize_model."""

    def test_serialize_model_datetime(self):
        """TC-UNIT-SER-001: Serialize a model with datetime fields.

        Verifies:
        - datetime fields are converted to ISO 8601 strings
        - UTC datetimes end with 'Z'
        - Non-datetime fields are preserved as-is
        """
        model = _FakeModel()
        result = serialize_model(model)

        assert isinstance(result, dict)
        assert result["id"] == "test-id-001"
        assert result["name"] == "测试"

        # Datetime fields should be ISO strings
        assert isinstance(result["created_at"], str)
        assert isinstance(result["updated_at"], str)

        # Should end with 'Z' for UTC
        assert result["created_at"].endswith("Z")
        assert result["updated_at"].endswith("Z")

        # Verify parseable
        parsed = datetime.fromisoformat(result["created_at"].replace("Z", "+00:00"))
        assert parsed.year == 2026
        assert parsed.month == 1
        assert parsed.day == 15

    def test_serialize_models_list(self):
        """TC-UNIT-SER-002: Serialize a list of models.

        Verifies:
        - Returns a list of dicts
        - Each dict has correct fields
        - List length matches input
        """
        models = [
            _FakeModel(id="id-1", name="模型A"),
            _FakeModel(id="id-2", name="模型B"),
            _FakeModel(id="id-3", name="模型C"),
        ]
        results = serialize_models(models)

        assert isinstance(results, list)
        assert len(results) == 3

        for i, result in enumerate(results):
            assert isinstance(result, dict)
            assert result["id"] == f"id-{i + 1}"
            assert isinstance(result["created_at"], str)

    def test_serialize_none(self):
        """TC-UNIT-SER-003: Serialize a model with None datetime values.

        Verifies:
        - If datetime fields are None, they remain None in output
        - Other fields are preserved correctly
        """

        class _NoneDatetimeModel(SQLModel):
            id: str = "test-id-003"
            name: str = "无时间模型"
            created_at: datetime | None = None
            updated_at: datetime | None = None

        model = _NoneDatetimeModel()
        result = serialize_model(model)

        assert result["id"] == "test-id-003"
        assert result["name"] == "无时间模型"
        # None datetimes should remain None
        assert result["created_at"] is None
        assert result["updated_at"] is None

    def test_serialize_naive_datetime(self):
        """TC-UNIT-SER-004: Serialize a model with naive (no timezone) datetime.

        Verifies:
        - Naive datetimes are treated as UTC
        - Output string ends with 'Z'
        """
        model = _NaiveDatetimeModel()
        result = serialize_model(model)

        assert isinstance(result["created_at"], str)
        assert result["created_at"].endswith("Z")

        # The naive datetime should be interpreted as UTC
        parsed = datetime.fromisoformat(result["created_at"].replace("Z", "+00:00"))
        assert parsed.year == 2026
        assert parsed.month == 3
        assert parsed.day == 10
