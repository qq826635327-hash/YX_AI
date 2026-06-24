r"""分镜拆分 + 实体关联写入 端到端测试。

用法（在 backend 目录下执行）：
    .venv\Scripts\python.exe scripts\test_shot_parsing_e2e.py

测试流程：
1. 在真实 app.db 中创建一个临时测试项目并写入示例剧本。
2. mock LLM 调用，返回预构造的角色/场景/道具/章节/分镜数据。
3. 调用 parse_script_async 跑完整解析流程。
4. 验证写入结果：分镜数量、shot_no 连续性、分镜与实体的关联表。
5. 删除测试项目及其目录，清理数据。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 将 backend 根目录加入模块搜索路径
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# 先初始化数据库与模型，确保表存在
from app.db import init_db

init_db()

from app.db import session_scope
from app.models import Project, ScriptDocument
from app.pipelines._orchestrator import parse_script_async
from app.pipelines import _extraction_stages, _orchestrator
from app.services.project_service import delete_project, init_project_directory
from app.core.config import get_settings


# ============================================================
# 测试数据：示例剧本
# ============================================================
SAMPLE_SCRIPT = """【雨巷·旧忆】

林远撑着一把油纸伞，独自走在青石巷的雨夜里。
昏黄的路灯把雨水照成银线，他的影子被拉得很长。
苏晚从茶馆的木门后探出头，手里攥着一只旧怀表。

林远停下脚步，回头望向她。
苏晚轻声说：“你还留着它？”
老站长坐在古镇茶馆的柜台后，低头擦拭着茶杯，像是什么也没听见。
"""


# ============================================================
# Mock LLM 响应
# ============================================================
MOCK_CHARACTERS = """[
  {
    "name": "林远",
    "gender": "男",
    "age": "28岁",
    "role": "主角",
    "description": "沉默内敛的青年，怀揣旧日遗憾回到故乡。",
    "appearance": "写实风格，黑色短发，眉宇微蹙，身穿深灰色风衣，撑着一把油纸伞，雨夜中神情落寞"
  },
  {
    "name": "苏晚",
    "gender": "女",
    "age": "26岁",
    "role": "主角",
    "description": "林远的旧识，在古镇茶馆等待多年。",
    "appearance": "写实风格，长发挽起，穿着青色旗袍，手中握着一只旧怀表，眼神温柔而忧伤"
  },
  {
    "name": "老站长",
    "gender": "男",
    "age": "60岁",
    "role": "配角",
    "description": "古镇茶馆的主人，见证了两人的重逢。",
    "appearance": "写实风格，白发，戴着老花镜，穿着棕色围裙，坐在柜台后低头擦茶杯"
  }
]"""

MOCK_SCENES = """[
  {
    "name": "青石巷雨夜",
    "visualPrompt": "江南古镇的青石板小巷，夜晚下着细雨，昏黄路灯照亮湿漉漉的石板路，两侧是白墙黑瓦的老屋，雨丝在灯光下泛着银光，氛围静谧忧伤"
  },
  {
    "name": "古镇茶馆",
    "visualPrompt": "古朴的中式茶馆内部，暖黄色灯光，木质桌椅，柜台上摆放着茶壶茶杯，墙上挂着旧照片，窗外可见雨夜街道，氛围温馨怀旧"
  }
]"""

MOCK_PROPS = """[
  {
    "name": "油纸伞",
    "visualPrompt": "传统中式油纸伞，深褐色竹柄，伞面为暗红色，绘有素雅梅花图案，伞骨清晰可见，质感温润"
  },
  {
    "name": "旧怀表",
    "visualPrompt": "复古黄铜怀表，表壳有细密雕花，表盘微微泛黄，指针停在某个时刻，表链略显陈旧"
  }
]"""

MOCK_EPISODES = """{
  "episodes": [
    {
      "title": "第1集：雨巷重逢",
      "chapters": [
        {"title": "雨夜独行", "start": 1, "end": 2, "plot": "林远撑伞走过雨巷"},
        {"title": "茶馆相望", "start": 3, "end": 4, "plot": "苏晚在茶馆门口出现，二人对视"}
      ]
    }
  ]
}"""

MOCK_SHOTS = """_::-OUTPUT_START::-_

_::-RECORD::-_

【原文对照】
(约 4 秒) 林远撑着一把油纸伞，独自走在青石巷的雨夜里。

出场人物：林远

【画面】写实风格，雨夜，【青石巷雨夜】，昏黄路灯照亮细雨，【林远】撑【油纸伞】独行，深灰色风衣，影子被拉得很长。

【首帧提示词】
写实风格，电影级写实质感，全景，【青石巷雨夜】，细雨绵绵，昏黄路灯照亮湿漉漉的青石板路，【林远】撑【油纸伞】从巷子深处走来，深灰色风衣，黑色短发，神情落寞，雨丝在灯光下泛着银光，白墙黑瓦老屋，氛围静谧忧伤，8K超高清

【尾帧提示词】
写实风格，电影级写实质感，中景，【青石巷雨夜】，【林远】停下脚步，微微侧头，昏黄路灯照亮半边脸，油纸伞微微倾斜，雨水顺着伞沿滴落，影子被拉得更长，8K超高清

【视频提示词】
写实风格，缓慢推镜头从全景推向【林远】背影，雨丝持续落下，【林远】脚步渐缓，伞面微微转动，路灯光影在湿漉漉石板路上摇曳，氛围静谧忧伤

【关联场景】青石巷雨夜

_::-RECORD::-_

【原文对照】
(约 3 秒) 昏黄的路灯把雨水照成银线，他的影子被拉得很长。

出场人物：林远

【画面】特写路灯与雨丝，【林远】的影子在青石板上拉长，空镜无对白。

【首帧提示词】
写实风格，电影级写实质感，特写，【青石巷雨夜】，昏黄路灯与密集雨丝，【林远】的影子被拉得很长，投射在湿漉漉青石板上，油纸伞边缘滴落水珠，8K超高清

【尾帧提示词】
写实风格，电影级写实质感，近景，【青石巷雨夜】，【林远】低头看着自己的影子，风衣下摆被雨水打湿，路灯在他身后形成光晕，8K超高清

【视频提示词】
写实风格，固定机位，雨丝从路灯前飘过，【林远】的影子慢慢拉长又缩短，水珠从油纸伞边缘滴落，节奏缓慢

【关联场景】青石巷雨夜

_::-RECORD::-_

【原文对照】
(约 5 秒) 苏晚从茶馆的木门后探出头，手里攥着一只旧怀表。

出场人物：苏晚

【画面】【古镇茶馆】门口，【苏晚】推门探身，青色旗袍，手中【旧怀表】在暖光中泛旧。

【首帧提示词】
写实风格，电影级写实质感，中景，【古镇茶馆】门口，暖黄色灯光从门内溢出，【苏晚】推开木门探出身子，青色旗袍，长发挽起，手中攥着【旧怀表】，神情温柔忧伤，雨夜街道在背景中虚化，8K超高清

【尾帧提示词】
写实风格，电影级写实质感，特写，【古镇茶馆】门口，【苏晚】低头凝视手中【旧怀表】，暖光映照在她脸上，怀表表链垂落，手指微微收紧，8K超高清

【视频提示词】
写实风格，缓慢推进到【苏晚】手部特写，木门轻轻晃动，【旧怀表】在暖光中微微反光，【苏晚】手指收紧表链，情绪细腻

【关联场景】古镇茶馆

_::-RECORD::-_

【原文对照】
(约 6 秒) 林远停下脚步，回头望向她。苏晚轻声说：“你还留着它？”

出场人物：林远、苏晚

【画面】【青石巷雨夜】与【古镇茶馆】交界处，【林远】转身，【苏晚】站在茶馆门口举着【旧怀表】，二人隔空相望。

【首帧提示词】
写实风格，电影级写实质感，全景，【青石巷雨夜】与【古镇茶馆】交界处，细雨绵绵，【林远】撑【油纸伞】转身望向茶馆方向，【苏晚】站在茶馆暖光门口，手中举着【旧怀表】，二人隔空相望，8K超高清

【尾帧提示词】
写实风格，电影级写实质感，近景，【林远】与【苏晚】面对面，油纸伞微微抬起，【旧怀表】在二人之间被暖光照亮，【林远】眼神复杂，【苏晚】眼含泪光，8K超高清

【视频提示词】
写实风格，缓慢横移镜头从【林远】身后绕至侧面，【林远】转身，【苏晚】走出茶馆半步，【旧怀表】在二人之间缓缓举起，雨夜氛围从冷调过渡为暖调

【关联场景】青石巷雨夜、古镇茶馆

_::-OUTPUT_END::-_
"""


# ============================================================
# Mock 函数
# ============================================================
def _build_mock_llm():
    """根据 stage 返回对应 mock 响应。"""
    from unittest.mock import AsyncMock

    async def mock_call_llm_stream(
        system_prompt: str,
        user_content: str,
        project_id: str,
        stage: str,
        temperature: float = 0.3,
        json_mode: bool = True,
        timeout_override: int | None = None,
    ) -> str:
        # 通过 stage 判断当前处于哪一阶段
        if stage == "character":
            # 角色/场景/道具提取共用 character stage，这里按 user_content 关键词区分
            if "角色" in system_prompt or "角色" in user_content[:200]:
                return MOCK_CHARACTERS
            if "场景" in system_prompt or "场景" in user_content[:200]:
                return MOCK_SCENES
            if "道具" in system_prompt or "道具" in user_content[:200]:
                return MOCK_PROPS
            return MOCK_CHARACTERS
        if stage == "episode":
            return MOCK_EPISODES
        if stage == "shot":
            return MOCK_SHOTS
        return ""

    async def mock_call_llm(
        system_prompt: str,
        user_content: str,
        temperature: float = 0.3,
        json_mode: bool = True,
        timeout_override: int | None = None,
    ) -> str:
        # 非流式 fallback，同样按关键词返回
        if "角色" in system_prompt:
            return MOCK_CHARACTERS
        if "场景" in system_prompt:
            return MOCK_SCENES
        if "道具" in system_prompt:
            return MOCK_PROPS
        if "分镜" in system_prompt or "shot" in system_prompt.lower():
            return MOCK_SHOTS
        if "章节" in system_prompt or "episode" in system_prompt.lower():
            return MOCK_EPISODES
        return ""

    return AsyncMock(side_effect=mock_call_llm_stream), AsyncMock(side_effect=mock_call_llm)


# ============================================================
# 主测试流程
# ============================================================
async def main() -> None:
    from sqlmodel import select
    from app.models import Character, Scene, Prop, Episode, Shot
    from app.models.shot_reference import ShotCharacter, ShotScene, ShotProp

    # 1. 创建临时测试项目（必须放在 projects_root_abs 下，否则 delete_project 拒绝删目录）
    settings = get_settings()
    test_root = settings.projects_root_abs / "test_shot_parsing_e2e"
    with session_scope() as session:
        project = Project(
            name="测试-分镜解析-20260623",
            description="临时项目，用于验证分镜拆分与实体关联写入",
            root_path=str(test_root),
            style_preset="realistic",
        )
        session.add(project)
        session.flush()
        session.refresh(project)
        project_id = project.id
        init_project_directory(Path(project.root_path))

        doc = ScriptDocument(
            project_id=project_id,
            raw_text=SAMPLE_SCRIPT,
            version=1,
        )
        session.add(doc)
        session.flush()
        session.refresh(doc)
        script_id = doc.id

    logger.info(f"已创建测试项目: {project_id}, 剧本: {script_id}")

    # 2. 安装 mock
    original_stream = _extraction_stages._call_llm_stream
    original_llm = _extraction_stages._call_llm
    original_find_llm = _orchestrator._find_text_llm_config

    mock_stream, mock_llm = _build_mock_llm()
    _extraction_stages._call_llm_stream = mock_stream
    _extraction_stages._call_llm = mock_llm
    _orchestrator._find_text_llm_config = lambda: ("http://localhost", "fake-key", "fake-model", 60)

    try:
        # 3. 执行解析
        await parse_script_async(script_id, project_id, preserve_prompts=False)

        # 4. 验证结果
        with session_scope() as session:
            characters = list(session.exec(select(Character).where(Character.project_id == project_id)).all())
            scenes = list(session.exec(select(Scene).where(Scene.project_id == project_id)).all())
            props = list(session.exec(select(Prop).where(Prop.project_id == project_id)).all())
            episodes = list(session.exec(select(Episode).where(Episode.project_id == project_id)).all())
            shots = list(session.exec(select(Shot).where(Shot.project_id == project_id).order_by(Shot.shot_no)).all())

            logger.info(f"实体写入: 角色={len(characters)}, 场景={len(scenes)}, 道具={len(props)}")
            logger.info(f"剧集={len(episodes)}, 分镜={len(shots)}")

            assert len(characters) == 3, f"期望 3 个角色，实际 {len(characters)}"
            assert len(scenes) == 2, f"期望 2 个场景，实际 {len(scenes)}"
            assert len(props) == 2, f"期望 2 个道具，实际 {len(props)}"
            assert len(shots) == 4, f"期望 4 个分镜，实际 {len(shots)}"

            # 验证 shot_no 连续
            shot_nos = [sh.shot_no for sh in shots]
            assert shot_nos == [1, 2, 3, 4], f"shot_no 不连续: {shot_nos}"

            # 验证关联表
            char_name_map = {c.id: c.name for c in characters}
            scene_name_map = {s.id: s.name for s in scenes}
            prop_name_map = {p.id: p.name for p in props}

            shot_id_to_no = {sh.id: sh.shot_no for sh in shots}

            shot_char_links = list(session.exec(select(ShotCharacter).where(ShotCharacter.shot_id.in_(shot_id_to_no))).all())
            shot_scene_links = list(session.exec(select(ShotScene).where(ShotScene.shot_id.in_(shot_id_to_no))).all())
            shot_prop_links = list(session.exec(select(ShotProp).where(ShotProp.shot_id.in_(shot_id_to_no))).all())

            logger.info(f"关联写入: ShotCharacter={len(shot_char_links)}, ShotScene={len(shot_scene_links)}, ShotProp={len(shot_prop_links)}")

            # 按 shot_no 分组打印关联
            def group_links(links, name_map):
                groups: dict[int, list[str]] = {}
                for link in links:
                    no = shot_id_to_no.get(link.shot_id)
                    if no is None:
                        continue
                    groups.setdefault(no, []).append(name_map.get(getattr(link, "character_id", getattr(link, "scene_id", getattr(link, "prop_id", ""))), "未知"))
                return groups

            char_groups = group_links(shot_char_links, char_name_map)
            scene_groups = group_links(shot_scene_links, scene_name_map)
            prop_groups = group_links(shot_prop_links, prop_name_map)

            logger.info("分镜关联详情:")
            for no in shot_nos:
                logger.info(
                    f"  分镜 {no}: 角色={char_groups.get(no, [])}, 场景={scene_groups.get(no, [])}, 道具={prop_groups.get(no, [])}"
                )

            # 关键断言
            assert 1 in char_groups and "林远" in char_groups[1], "分镜1 应关联角色林远"
            assert 4 in char_groups and "林远" in char_groups[4] and "苏晚" in char_groups[4], "分镜4 应同时关联林远和苏晚"
            assert 1 in scene_groups and "青石巷雨夜" in scene_groups[1], "分镜1 应关联场景青石巷雨夜"
            assert 4 in prop_groups and "旧怀表" in prop_groups[4], "分镜4 应关联道具旧怀表"
            assert "油纸伞" in prop_groups.get(1, []), "分镜1 应关联道具油纸伞"

            logger.info("✅ 所有断言通过")

    finally:
        # 5. 还原 mock
        _extraction_stages._call_llm_stream = original_stream
        _extraction_stages._call_llm = original_llm
        _orchestrator._find_text_llm_config = original_find_llm

        # 6. 清理测试项目
        with session_scope() as session:
            deleted = delete_project(session, project_id, delete_files=True)
            logger.info(f"测试项目清理: {'已删除' if deleted else '删除失败'}")


if __name__ == "__main__":
    asyncio.run(main())
