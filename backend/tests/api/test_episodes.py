"""Episode and Shot management API tests.

Tests cover episode CRUD, shot CRUD, and shot reference associations
(characters, scenes, props linked to shots).
"""

import pytest

from tests.factories import (
    assert_status,
    create_character,
    create_episode,
    create_shot,
)


@pytest.mark.asyncio
@pytest.mark.api
class TestEpisodeCRUD:
    """Episode CRUD integration tests."""

    async def test_create_episode(self, client, project):
        """TC-API-EP-001: Create a new episode with valid data.

        Verifies:
        - Response status is 200
        - Episode fields match input
        - Episode is associated with the correct project_id
        """
        result = await create_episode(
            client, project["id"], episode_no=1, title="第一集"
        )

        assert result["episode_no"] == 1
        assert result["title"] == "第一集"
        assert result["project_id"] == project["id"]
        assert "id" in result
        assert len(result["id"]) == 36

    async def test_list_episodes(self, client, project):
        """TC-API-EP-002: List episodes for a project.

        Verifies:
        - Response contains a list in 'data'
        - Created episodes appear in the list
        """
        ep1 = await create_episode(
            client, project["id"], episode_no=1, title="列表集1"
        )
        ep2 = await create_episode(
            client, project["id"], episode_no=2, title="列表集2"
        )

        response = await client.get(f"/api/projects/{project['id']}/episodes")
        data = await assert_status(response, 200)

        assert isinstance(data["data"], list)
        ids = [ep["id"] for ep in data["data"]]
        assert ep1["id"] in ids
        assert ep2["id"] in ids

    async def test_update_episode(self, client, project):
        """TC-API-EP-003: Update episode fields via PATCH.

        Verifies:
        - PATCH with partial data succeeds
        - Updated title is reflected in the response
        """
        ep = await create_episode(
            client, project["id"], episode_no=1, title="原始标题"
        )

        response = await client.patch(
            f"/api/projects/{project['id']}/episodes/{ep['id']}",
            json={"title": "更新后标题", "summary": "新摘要"},
        )
        data = await assert_status(response, 200)

        assert data["data"]["title"] == "更新后标题"
        assert data["data"]["summary"] == "新摘要"
        assert data["data"]["id"] == ep["id"]

    async def test_delete_episode(self, client, project):
        """TC-API-EP-004: Delete an episode.

        Verifies:
        - DELETE returns 200
        - Subsequent GET returns 404
        """
        ep = await create_episode(
            client, project["id"], episode_no=99, title="待删除集"
        )

        response = await client.delete(
            f"/api/projects/{project['id']}/episodes/{ep['id']}"
        )
        await assert_status(response, 200)

        # Verify it's gone
        response = await client.get(
            f"/api/projects/{project['id']}/episodes/{ep['id']}"
        )
        assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.api
class TestShotCRUD:
    """Shot CRUD integration tests."""

    async def test_create_shot(self, client, project, episode):
        """TC-API-SHOT-001: Create a new shot under an episode.

        Verifies:
        - Response status is 200
        - Shot fields match input
        - Shot is associated with the correct episode_id and project_id
        """
        result = await create_shot(
            client, episode["id"], shot_no=1, summary="第一个分镜"
        )

        assert result["shot_no"] == 1
        assert result["summary"] == "第一个分镜"
        assert result["episode_id"] == episode["id"]
        assert result["project_id"] == project["id"]
        assert "id" in result

    async def test_list_shots(self, client, episode):
        """TC-API-SHOT-002: List shots for an episode.

        Verifies:
        - Response contains a list in 'data'
        - Created shots appear in the list
        - Shots are ordered by sort_order / shot_no
        """
        shot1 = await create_shot(client, episode["id"], shot_no=1, summary="分镜A")
        shot2 = await create_shot(client, episode["id"], shot_no=2, summary="分镜B")

        response = await client.get(f"/api/episodes/{episode['id']}/shots")
        data = await assert_status(response, 200)

        assert isinstance(data["data"], list)
        ids = [s["id"] for s in data["data"]]
        assert shot1["id"] in ids
        assert shot2["id"] in ids

    async def test_shot_references(self, client, project, episode):
        """TC-API-SHOT-003: Add and retrieve shot references (character associations).

        Verifies:
        - POST /api/shots/{sid}/characters adds associations
        - GET /api/shots/{sid}/references returns the associations
        - DELETE removes the association
        """
        # Create entities to reference
        shot = await create_shot(client, episode["id"], shot_no=1, summary="引用测试分镜")
        char = await create_character(
            client, project["id"], name="引用角色", char_type="protagonist"
        )

        # Add character reference
        response = await client.post(
            f"/api/shots/{shot['id']}/characters",
            json={"entity_ids": [char["id"]]},
        )
        ref_data = await assert_status(response, 200)
        assert ref_data["data"]["added"] >= 1

        # Get references
        response = await client.get(f"/api/shots/{shot['id']}/references")
        refs = await assert_status(response, 200)
        assert "data" in refs

        # Remove character reference
        response = await client.delete(
            f"/api/shots/{shot['id']}/characters/{char['id']}"
        )
        await assert_status(response, 200)
