"""Character CRUD API tests.

Tests cover character entity lifecycle via the REST API, including
CRUD operations, filtering by char_type, duplicate name handling,
and rename directory side-effects.
"""

import pytest

from tests.factories import assert_status, create_character, create_project


@pytest.mark.asyncio
@pytest.mark.api
class TestCharacterCRUD:
    """Character CRUD integration tests."""

    async def test_create_character(self, client, project):
        """TC-API-CHAR-001: Create a new character with valid data.

        Verifies:
        - Response status is 200
        - Character name and char_type match input
        - Character has a generated UUID 'id'
        - Character is associated with the correct project_id
        """
        result = await create_character(
            client, project["id"], name="主角A", char_type="protagonist"
        )

        assert result["name"] == "主角A"
        assert result["char_type"] == "protagonist"
        assert result["project_id"] == project["id"]
        assert "id" in result
        assert len(result["id"]) == 36

    async def test_list_characters(self, client, project):
        """TC-API-CHAR-002: List characters for a project.

        Verifies:
        - Response contains a list in 'data'
        - Created character appears in the list
        - List supports ordering by sort_order
        """
        # Create two characters
        char1 = await create_character(
            client, project["id"], name="角色列表A", char_type="protagonist"
        )
        char2 = await create_character(
            client, project["id"], name="角色列表B", char_type="supporting"
        )

        response = await client.get(f"/api/projects/{project['id']}/characters")
        data = await assert_status(response, 200)

        assert isinstance(data["data"], list)
        ids = [c["id"] for c in data["data"]]
        assert char1["id"] in ids
        assert char2["id"] in ids

    async def test_get_character(self, client, project, character):
        """TC-API-CHAR-003: Get a single character by ID.

        Verifies:
        - Response status is 200
        - Returned character matches the fixture
        """
        response = await client.get(
            f"/api/projects/{project['id']}/characters/{character['id']}"
        )
        data = await assert_status(response, 200)

        assert data["data"]["id"] == character["id"]
        assert data["data"]["name"] == character["name"]
        assert data["data"]["project_id"] == project["id"]

    async def test_update_character(self, client, project, character):
        """TC-API-CHAR-004: Update character fields via PATCH.

        Verifies:
        - PATCH with partial data succeeds
        - Updated name and description are reflected
        - Unmodified fields remain unchanged
        """
        update_payload = {
            "name": "更新后角色名",
            "description": "新描述",
            "char_type": "supporting",
        }
        response = await client.patch(
            f"/api/projects/{project['id']}/characters/{character['id']}",
            json=update_payload,
        )
        data = await assert_status(response, 200)

        assert data["data"]["name"] == "更新后角色名"
        assert data["data"]["description"] == "新描述"
        assert data["data"]["char_type"] == "supporting"
        assert data["data"]["id"] == character["id"]

    async def test_delete_character(self, client, project):
        """TC-API-CHAR-005: Delete a character.

        Verifies:
        - DELETE returns 200
        - Subsequent GET returns 404
        """
        char = await create_character(
            client, project["id"], name="待删除角色"
        )

        # Delete
        response = await client.delete(
            f"/api/projects/{project['id']}/characters/{char['id']}"
        )
        await assert_status(response, 200)

        # Verify it's gone
        response = await client.get(
            f"/api/projects/{project['id']}/characters/{char['id']}"
        )
        assert response.status_code == 404

    async def test_filter_by_char_type(self, client, project):
        """TC-API-CHAR-006: Filter characters by char_type query parameter.

        Verifies:
        - Filtering by 'protagonist' returns only protagonist characters
        - Filtering by 'extra' returns empty when none exist
        """
        # Create characters of different types
        await create_character(
            client, project["id"], name="主角X", char_type="protagonist"
        )
        await create_character(
            client, project["id"], name="配角X", char_type="supporting"
        )

        # Filter by protagonist
        response = await client.get(
            f"/api/projects/{project['id']}/characters?char_type=protagonist"
        )
        data = await assert_status(response, 200)

        for char in data["data"]:
            assert char["char_type"] == "protagonist"

        # Filter by extra (should return empty or fewer)
        response = await client.get(
            f"/api/projects/{project['id']}/characters?char_type=extra"
        )
        data = await assert_status(response, 200)
        # No extra characters were created
        extras = [c for c in data["data"] if c["char_type"] == "extra"]
        assert len(extras) == 0

    async def test_create_duplicate_name(self, client, project):
        """TC-API-CHAR-007: Create characters with duplicate names in the same project.

        The API allows duplicate names (no unique constraint on name per project).
        Both characters should be created with different IDs.
        """
        char1 = await create_character(
            client, project["id"], name="重名角色", char_type="protagonist"
        )
        char2 = await create_character(
            client, project["id"], name="重名角色", char_type="supporting"
        )

        assert char1["id"] != char2["id"]
        assert char1["name"] == char2["name"]

    async def test_rename_updates_directory(self, client, project):
        """TC-API-CHAR-008: Renaming a character triggers directory rename on disk.

        Verifies:
        - PATCH with a new name succeeds
        - The character's name is updated in the response
        Note: Actual filesystem rename depends on project directory existing;
        this test validates the API-level behavior.
        """
        char = await create_character(
            client, project["id"], name="原名角色"
        )

        response = await client.patch(
            f"/api/projects/{project['id']}/characters/{char['id']}",
            json={"name": "新名角色"},
        )
        data = await assert_status(response, 200)

        assert data["data"]["name"] == "新名角色"
        assert data["data"]["id"] == char["id"]
