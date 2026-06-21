"""Project CRUD API tests.

Tests cover the full lifecycle of project entities via the REST API:
create, list, get, update, delete, and edge cases.
"""

import pytest

from tests.factories import assert_status, create_project


@pytest.mark.asyncio
@pytest.mark.api
class TestProjectCRUD:
    """Project CRUD integration tests."""

    async def test_create_project(self, client):
        """TC-API-PROJ-001: Create a new project with valid data.

        Verifies:
        - Response status is 200
        - Response contains 'data' with project fields
        - Project name matches the input
        - Project has a generated UUID 'id'
        - Project status defaults to 'active'
        """
        result = await create_project(client, name="创建项目测试")
        project_id = result["id"]

        try:
            assert result["name"] == "创建项目测试"
            assert result["status"] == "active"
            assert "id" in result
            assert len(result["id"]) == 36  # UUID format
            assert "created_at" in result
            assert "updated_at" in result
            assert "root_path" in result
        finally:
            # Cleanup
            await client.delete(f"/api/projects/{project_id}")

    async def test_list_projects(self, client):
        """TC-API-PROJ-002: List projects with pagination.

        Verifies:
        - Response contains paginated data structure
        - 'items' is a list
        - 'total' is an integer >= 0
        - Created project appears in the list
        """
        # Create a project to ensure the list is non-empty
        result = await create_project(client, name="列表项目测试")
        project_id = result["id"]

        try:
            response = await client.get("/api/projects")
            data = await assert_status(response, 200)

            # Paginated response structure
            assert "data" in data
            page_data = data["data"]
            assert "items" in page_data
            assert "total" in page_data
            assert "page" in page_data
            assert "page_size" in page_data
            assert isinstance(page_data["items"], list)
            assert page_data["total"] >= 1

            # Our project should be in the list
            ids = [item["id"] for item in page_data["items"]]
            assert project_id in ids
        finally:
            await client.delete(f"/api/projects/{project_id}")

    async def test_get_project(self, client, project):
        """TC-API-PROJ-003: Get a single project by ID.

        Verifies:
        - Response status is 200
        - Returned project ID matches the requested ID
        - All expected fields are present
        """
        response = await client.get(f"/api/projects/{project['id']}")
        data = await assert_status(response, 200)

        assert data["data"]["id"] == project["id"]
        assert data["data"]["name"] == project["name"]
        assert "root_path" in data["data"]
        assert "character_count" in data["data"]
        assert "scene_count" in data["data"]
        assert "prop_count" in data["data"]
        assert "episode_count" in data["data"]
        assert "shot_count" in data["data"]

    async def test_update_project(self, client, project):
        """TC-API-PROJ-004: Update project fields via PATCH.

        Verifies:
        - PATCH with partial data succeeds
        - Updated fields are reflected in the response
        - Unmodified fields remain unchanged
        """
        update_payload = {
            "name": "更新后项目名称",
            "description": "更新后的描述",
        }
        response = await client.patch(
            f"/api/projects/{project['id']}", json=update_payload
        )
        data = await assert_status(response, 200)

        assert data["data"]["name"] == "更新后项目名称"
        assert data["data"]["description"] == "更新后的描述"
        # ID should not change
        assert data["data"]["id"] == project["id"]

    async def test_delete_project(self, client):
        """TC-API-PROJ-005: Delete a project.

        Verifies:
        - DELETE returns 200
        - Subsequent GET returns 404
        """
        # Create a project to delete
        result = await create_project(client, name="待删除项目")
        project_id = result["id"]

        # Delete
        response = await client.delete(f"/api/projects/{project_id}")
        await assert_status(response, 200)

        # Verify it's gone
        response = await client.get(f"/api/projects/{project_id}")
        assert response.status_code == 404

    async def test_create_duplicate_name(self, client):
        """TC-API-PROJ-006: Create projects with duplicate names.

        The API should allow duplicate names (names are not unique-constrained
        at the DB level for projects). Both projects should be created successfully.
        """
        result1 = await create_project(client, name="重名项目")
        result2 = await create_project(client, name="重名项目")

        try:
            # Both should succeed but have different IDs
            assert result1["id"] != result2["id"]
            assert result1["name"] == result2["name"]
        finally:
            await client.delete(f"/api/projects/{result1['id']}")
            await client.delete(f"/api/projects/{result2['id']}")

    async def test_get_nonexistent(self, client):
        """TC-API-PROJ-007: Get a project that does not exist.

        Verifies:
        - Response status is 404
        """
        response = await client.get("/api/projects/nonexistent-id-12345")
        assert response.status_code == 404
