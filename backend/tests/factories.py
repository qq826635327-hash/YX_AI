"""Test helper factories for creating entities via the API.

Each function sends an HTTP request to the test server and returns
the parsed JSON data from the response.
"""

from __future__ import annotations

from typing import Optional

import httpx


async def assert_status(response: httpx.Response, expected_status: int = 200) -> dict:
    """Assert the HTTP response status code and return parsed JSON.

    Args:
        response: The httpx response object.
        expected_status: Expected HTTP status code (default 200).

    Returns:
        Parsed JSON response body as a dict.

    Raises:
        AssertionError: If the status code does not match.
    """
    assert response.status_code == expected_status, (
        f"Expected status {expected_status}, got {response.status_code}. "
        f"Response body: {response.text[:500]}"
    )
    return response.json()


async def create_project(
    client: httpx.AsyncClient,
    name: str = "测试项目",
    description: Optional[str] = None,
) -> dict:
    """Create a project via POST /api/projects.

    Args:
        client: Async HTTP client.
        name: Project name.
        description: Optional project description.

    Returns:
        The created project data dict (from response 'data' field).
    """
    payload = {"name": name}
    if description:
        payload["description"] = description

    response = await client.post("/api/projects", json=payload)
    result = await assert_status(response, 200)
    return result["data"]


async def create_character(
    client: httpx.AsyncClient,
    project_id: str,
    name: str = "测试角色",
    char_type: str = "protagonist",
    description: Optional[str] = None,
) -> dict:
    """Create a character via POST /api/projects/{pid}/characters.

    Args:
        client: Async HTTP client.
        project_id: Parent project ID.
        name: Character name.
        char_type: Character type (protagonist/supporting/extra).
        description: Optional character description.

    Returns:
        The created character data dict.
    """
    payload = {"name": name, "char_type": char_type}
    if description:
        payload["description"] = description

    response = await client.post(
        f"/api/projects/{project_id}/characters", json=payload
    )
    result = await assert_status(response, 200)
    return result["data"]


async def create_scene(
    client: httpx.AsyncClient,
    project_id: str,
    name: str = "测试场景",
    description: Optional[str] = None,
) -> dict:
    """Create a scene via POST /api/projects/{pid}/scenes.

    Args:
        client: Async HTTP client.
        project_id: Parent project ID.
        name: Scene name.
        description: Optional scene description.

    Returns:
        The created scene data dict.
    """
    payload = {"name": name}
    if description:
        payload["description"] = description

    response = await client.post(
        f"/api/projects/{project_id}/scenes", json=payload
    )
    result = await assert_status(response, 200)
    return result["data"]


async def create_prop(
    client: httpx.AsyncClient,
    project_id: str,
    name: str = "测试道具",
    description: Optional[str] = None,
) -> dict:
    """Create a prop via POST /api/projects/{pid}/props.

    Args:
        client: Async HTTP client.
        project_id: Parent project ID.
        name: Prop name.
        description: Optional prop description.

    Returns:
        The created prop data dict.
    """
    payload = {"name": name}
    if description:
        payload["description"] = description

    response = await client.post(
        f"/api/projects/{project_id}/props", json=payload
    )
    result = await assert_status(response, 200)
    return result["data"]


async def create_episode(
    client: httpx.AsyncClient,
    project_id: str,
    episode_no: int = 1,
    title: str = "第1集",
    summary: Optional[str] = None,
) -> dict:
    """Create an episode via POST /api/projects/{pid}/episodes.

    Args:
        client: Async HTTP client.
        project_id: Parent project ID.
        episode_no: Episode number (must be >= 1).
        title: Episode title.
        summary: Optional episode summary.

    Returns:
        The created episode data dict.
    """
    payload = {"episode_no": episode_no, "title": title}
    if summary:
        payload["summary"] = summary

    response = await client.post(
        f"/api/projects/{project_id}/episodes", json=payload
    )
    result = await assert_status(response, 200)
    return result["data"]


async def create_shot(
    client: httpx.AsyncClient,
    episode_id: str,
    shot_no: int = 1,
    summary: str = "测试分镜",
    first_frame_prompt: Optional[str] = None,
) -> dict:
    """Create a shot via POST /api/episodes/{eid}/shots.

    Args:
        client: Async HTTP client.
        episode_id: Parent episode ID.
        shot_no: Shot number (must be >= 1).
        summary: Shot summary/description.
        first_frame_prompt: Optional first frame prompt text.

    Returns:
        The created shot data dict.
    """
    payload: dict = {"shot_no": shot_no, "summary": summary}
    if first_frame_prompt:
        payload["first_frame_prompt"] = first_frame_prompt

    response = await client.post(
        f"/api/episodes/{episode_id}/shots", json=payload
    )
    result = await assert_status(response, 200)
    return result["data"]
