"""pytest 全局 fixtures。

提供数据库引擎、会话（事务回滚隔离）、HTTP 客户端以及常用实体工厂。
所有 API 测试通过 httpx.AsyncClient 连接运行中的测试服务器（http://127.0.0.1:8000）。
"""

from __future__ import annotations

import asyncio
from typing import Iterator

import httpx
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy import event

from app.models import (
    Character,
    Episode,
    Project,
    Prop,
    Scene,
    Shot,
    Asset,
    GenerationTask,
    TaskLog,
    ApiProvider,
    WorkflowMapping,
    ShotCharacter,
    ShotScene,
    ShotProp,
    ScriptDocument,
)


# ============================================================
# Event loop fixture (session scope for async tests)
# ============================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================
# Database engine (session scope - in-memory SQLite)
# ============================================================

@pytest.fixture(scope="session")
def engine():
    """Create an in-memory SQLite engine for testing.

    Uses check_same_thread=False for async compatibility.
    Enables foreign keys via PRAGMA on each connection.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables once for the session
    SQLModel.metadata.create_all(test_engine)

    yield test_engine

    test_engine.dispose()


# ============================================================
# Database session (function scope - transaction rollback)
# ============================================================

@pytest.fixture()
def session(engine) -> Iterator[Session]:
    """Provide a DB session with transaction rollback for test isolation.

    Each test gets a fresh transaction that is rolled back on teardown,
    ensuring no side-effects leak between tests.
    """
    from sqlmodel import Session as SQLModelSession

    connection = engine.connect()
    transaction = connection.begin()

    session = SQLModelSession(bind=connection, expire_on_commit=False)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ============================================================
# HTTP client (session scope)
# ============================================================

@pytest.fixture(scope="session")
async def client():
    """Provide an async HTTP client connected to the test server.

    Connects to http://127.0.0.1:8000 where the backend is expected
    to be running during integration test execution.
    """
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000",
        timeout=30.0,
    ) as http_client:
        yield http_client


# ============================================================
# Entity factory fixtures (function scope)
# ============================================================

@pytest.fixture()
async def project(client) -> dict:
    """Create a test project and return its data.

    Automatically cleaned up after the test by deleting via API.
    """
    from tests.factories import create_project

    data = await create_project(client, name="测试项目_fixture")
    yield data

    # Cleanup
    project_id = data.get("id")
    if project_id:
        await client.delete(f"/api/projects/{project_id}")


@pytest.fixture()
async def character(client, project) -> dict:
    """Create a test character under the test project."""
    from tests.factories import create_character

    data = await create_character(
        client, project["id"], name="测试角色_fixture", char_type="protagonist"
    )
    yield data


@pytest.fixture()
async def scene(client, project) -> dict:
    """Create a test scene under the test project."""
    from tests.factories import create_scene

    data = await create_scene(client, project["id"], name="测试场景_fixture")
    yield data


@pytest.fixture()
async def prop(client, project) -> dict:
    """Create a test prop under the test project."""
    from tests.factories import create_prop

    data = await create_prop(client, project["id"], name="测试道具_fixture")
    yield data


@pytest.fixture()
async def episode(client, project) -> dict:
    """Create a test episode under the test project."""
    from tests.factories import create_episode

    data = await create_episode(
        client, project["id"], episode_no=1, title="第1集_fixture"
    )
    yield data


@pytest.fixture()
async def shot(client, episode) -> dict:
    """Create a test shot under the test episode."""
    from tests.factories import create_shot

    data = await create_shot(client, episode["id"], shot_no=1, summary="测试分镜_fixture")
    yield data
