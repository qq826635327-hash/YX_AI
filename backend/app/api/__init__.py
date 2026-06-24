"""API 路由聚合。"""

from fastapi import APIRouter

from app.api import (
    assets,
    characters,
    episodes,
    generate,
    image_hosting,
    logs,
    perf,
    projects,
    prompt_templates,
    props,
    scenes,
    script,
    settings as settings_api,
    shot_references,
    shots,
    style_presets,
    tasks,
    workflows,
    providers,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(projects.router)
api_router.include_router(script.router)
api_router.include_router(characters.router)
api_router.include_router(scenes.router)
api_router.include_router(props.router)
api_router.include_router(episodes.router)
api_router.include_router(shots.router)
api_router.include_router(shot_references.router)
api_router.include_router(generate.router)
api_router.include_router(tasks.router)
api_router.include_router(assets.router)
api_router.include_router(providers.router)
api_router.include_router(image_hosting.router)
api_router.include_router(prompt_templates.router)
api_router.include_router(style_presets.router)
api_router.include_router(workflows.router)
api_router.include_router(settings_api.router)
api_router.include_router(logs.router)
api_router.include_router(perf.router)
