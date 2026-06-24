"""提示词模板服务。

提供提示词模板的增删改查、默认模板管理、内置模板初始化。
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlmodel import Session, select

from app.models import PromptTemplate
from app.models.prompt_template import PROMPT_TEMPLATE_TYPES
from app.schemas.prompt_template import PromptTemplateCreate, PromptTemplateUpdate

logger = logging.getLogger(__name__)


# ============================================================
# 内置模板（与前端默认配置保持一致）
# ============================================================

BUILTIN_TEMPLATES: list[dict] = [
    {
        "name": "内置默认-角色提取",
        "template_type": "character",
        "description": "从剧本/小说文本中提取所有人物角色信息，包含性别、年龄、外貌提示词",
        "is_default": True,
        "sort_order": 0,
        "content": """你是一个专业的角色分析师。根据用户提供的剧本/小说文本，提取文中出现过的所有人物角色。

要求：
1. 囊括文中提到的所有人物（包括第一人称"我"、旁白提到的人物等）
2. 人物可能有多种代称，需要识别并归纳
3. gender 必须明确：男/女/其他
4. age 必须明确：如"25岁""少年""中年""老年"等，如果文中未明确，请根据角色性格和故事背景合理推断
5. appearance 是用于 AI 生成角色立绘的提示词，必须详细：包含发色、发型、眼睛颜色、上身服装、下身服装、体态、配饰、标志性特征等
6. appearance 中必须体现该角色的画风特征（如{{style_hint}}），使生成的角色形象与整体画风一致
7. description 是角色的文字描述，包含性格、背景、身份等非视觉信息，用于展示和理解角色
8. 如果文中未明确描述某些外貌特征，请根据角色性别、年龄、性格和故事背景合理推断
9. 每个角色的着装必须有区分度，不能雷同
10. role 字段按角色重要程度判定：主角（核心角色）、配角（重要配角）、群演（出场较少）
11. **变身/变装/不同形态处理**：如果同一个角色在剧情中存在明显不同的外貌形态（如变身、变装、年龄变化、觉醒前后等），必须将每种形态作为独立条目输出，name 用"角色名（形态描述）"区分，例如"哪吒（莲花童子形态）"和"哪吒（三头六臂形态）"。每个条目的 appearance 只描述该形态下的外貌，不要混合多种形态。
12. **命名与外貌合规（防下游审核拦截）**：角色名（含形态描述）与 appearance 都不得出现 血/伤/鬼/魔/妖/煞/尸 等血腥、恐怖、灵异字眼（如「血魔」→「赤魔」、「鬼王」→「幽主」、「浑身血污/满身伤痕」→「衣衫沾尘」）；appearance 仍照常写性别、年龄、发色、瞳色、服饰等外貌（这是生成立绘所需，必须保留），只是规避血腥恐怖措辞。该中性命名将作为全片统一标识被下游分镜引用，请一次定稿。

请严格按以下 JSON 数组格式返回（不要包含其他文字，只返回纯 JSON）：

```json
[
  {
    "name": "角色名 或 角色名（形态描述）",
    "gender": "男|女|其他",
    "age": "年龄描述（如25岁、少年、中年等）",
    "role": "主角|配角|群演",
    "description": "角色性格、背景、身份等文字描述（非视觉信息）",
    "appearance": "该形态下的详细外貌描述（画风：{{style_hint}}，发型、发色、瞳色、肤色、体态、上身服装、下身服装、配饰、标志性特征等），只描述单一形态"
  }
]
```

剧本文本：
{{script_text}}
""",
    },
    {
        "name": "内置默认-场景提取",
        "template_type": "scene",
        "description": "从剧本/小说文本中提取所有主要场景",
        "is_default": True,
        "sort_order": 0,
        "content": """根据用户提供的剧本/小说内容，推导出文中出现过的所有主要场景。场景可能有多种代称，需要识别并归纳。

要求：
1. 囊括文中提到的所有主要场景
2. visualPrompt 是用于 AI 生成场景背景图的提示词，必须是纯环境视觉描述，需要包含位置、时间、光影、建筑、色调、氛围、布景道具等全部视觉要素，绝对不能包含任何人物描述、人名或剧情内容
3. 场景名称必须在四个字以上，避免潜在的重复
4. 每个场景的描述要有区分度，不能雷同
5. **命名与描述合规（防下游审核拦截）**：场景名称（name）与 visualPrompt 都不得出现 血/伤/鬼/魔/妖/煞/尸/阴森 等血腥、恐怖、灵异字眼，否则下游图片/视频生成会被内容审核拦截。命名遇到这类字时改用中性同义：「鬼/诡」→「幽/灵/暗」（如「诡物森林」→「幽暗密林」、「鬼境」→「灵境」），血腥恐怖氛围改写为「幽暗、压抑、雾气弥漫」等中性环境词。该中性命名将作为全片统一标识被下游分镜引用，请一次定稿。

以下是输出的 JSON 样例：

```json
[
  {
    "name": "学校校园外景",
    "visualPrompt": "现代都市中学校园，白天，阳光明媚，青春活力的氛围，三层教学楼，红色砖墙，绿树环绕，操场上有篮球架"
  },
  {
    "name": "家里客厅内部",
    "visualPrompt": "温馨的普通住宅家庭客厅，夜晚，暖黄色灯光，温馨舒适的氛围，沙发、茶几、电视，墙上挂着全家福"
  },
  {
    "name": "咖啡厅内部",
    "visualPrompt": "闹市区的文艺咖啡厅，下午，柔和的暖光，文艺安静的氛围，木质桌椅，墙上挂着抽象画，空气中弥漫着咖啡香气"
  }
]
```

请严格按上述 JSON 格式返回，只输出 JSON，不要包含其他文字。

剧本文本：
{{script_text}}
""",
    },
    {
        "name": "内置默认-道具提取",
        "template_type": "prop",
        "description": "从剧本/小说文本中提取所有重要道具/物品",
        "is_default": True,
        "sort_order": 0,
        "content": """你是一个专业的道具分析师。根据用户提供的剧本内容，提取文中出现过的所有重要物品/道具。

要求：
1. 囊括文中提到的所有关键物品（如武器、装备、信物、法宝、交通工具、日常物品、特殊道具等）
2. 物品可能有多种代称，需要识别并归纳为同一条目
3. visualPrompt 是用于 AI 生成道具图的提示词，必须是纯外观视觉描述：包含形状、材质纹理、颜色、尺寸、装饰、标志性特征等
4. visualPrompt 中不能包含任何人名或人物描述
5. **命名与描述合规（防下游审核拦截）**：道具名称（name）与 visualPrompt 都不得出现 血/鬼/魔/妖/煞/尸 等血腥、恐怖、灵异字眼，否则下游图片/视频生成会被内容审核拦截。命名遇到这类字时改用中性同义（如「噬血刀」→「赤纹刃」、「鬼面盾」→「兽面盾」、「尸魇幡」→「幽魂幡」），血腥/恐怖外观改写为中性材质纹理与色泽描述。该中性命名将作为全片统一标识被下游分镜引用，请一次定稿。

请严格按以下 JSON 数组格式返回（不要包含其他文字，只返回纯 JSON）：

```json
[
  {
    "name": "物品名称",
    "visualPrompt": "详细外观描述（形状、材质纹理、颜色、装饰、标志性特征等，不含人物）"
  }
]
```

剧本文本：
{{script_text}}
""",
    },
    {
        "name": "内置默认-章节划分",
        "template_type": "episode",
        "description": "根据分镜文案的内容结构进行智能剧集与章节划分",
        "is_default": True,
        "sort_order": 0,
        "content": """你是一个专业的视频制作助手，需要根据分镜文案和总分镜数进行智能剧集与章节划分。

任务要求：
1. 根据分镜文案的内容结构，将 {{total_shots}} 个分镜合理划分成若干剧集和章节
2. 每个章节应该包含完整的故事情节段落，避免在情节中间断开
3. 为每个章节生成简洁明确的标题和情节描述
4. 每个章节的分镜数量不应该超过 50 个，如果一个情节超过了 50 个分镜，就进行上中下的切分
5. 确保所有分镜都被包含在章节中，不能遗漏
6. 如果分镜总数较少（≤50），可以只创建一个剧集
7. 如果分镜总数较多，按故事的大情节段落（起承转合）划分成多集，每集包含若干章节

输出格式要求：
请严格按照以下 JSON 格式输出，不要包含任何其他文字：

```json
{
  "episodes": [
    {
      "title": "第1集：起源篇",
      "chapters": [
        {
          "title": "开篇：背景介绍",
          "start": 1,
          "end": 15,
          "plot": "开场介绍主角背景和故事设定"
        },
        {
          "title": "转折：冲突爆发",
          "start": 16,
          "end": 30,
          "plot": "冲突爆发，主角面临挑战"
        }
      ]
    }
  ]
}
```

重要约束：
- 第一个章节的 start 必须是 1，最后一个章节的 end 必须是 {{total_shots}}
- 相邻章节的编号必须连续（前一章 end + 1 = 后一章 start）
- 章节顺序必须与分镜的叙事顺序一致

分镜文案：
{{script_text}}

总分镜数：{{total_shots}}
""",
    },
    {
        "name": "内置默认-分镜拆分",
        "template_type": "shot",
        "description": "将剧本文案逐段转换为短视频分镜，并生成首帧/尾帧/视频提示词",
        "is_default": True,
        "sort_order": 0,
        "content": """你是拥有15年院线电影、头部纪录片实操经验的资深分镜指导与影视视听语言讲师，精通电影叙事语法、镜头语言逻辑与短视频情绪节奏。你的任务是将用户提供的视频旁白剧本，逐段转化为可直接用于AI文生图、图生图、文生视频的高质量工业级分镜脚本。

## 核心任务

严格依据原始旁白文本的语义、语句顺序与叙事逻辑，逐段拆解为分镜。每个分镜对应一段原生旁白。
- 完全保留原始旁白文本，不做润色、修改、增删或调整语句
- 画面设计不重复旁白字面信息，必须补充潜台词、氛围细节与视觉符号
- 实现声画错位高级叙事：画面节奏领先旁白半步，用镜头铺垫情绪与细节，再以旁白落点升华主旨

## 分镜创作硬性准则

### 一、视听匹配
- 核心剧情、关键细节、人物情绪、重点信息 → 特写/近景
- 人物动作、日常叙事、人物互动 → 中景
- 场景环境、时空背景、整体氛围 → 全景/远景/大远景
- 抽象概念（岁月、命运、遗憾、坚守等）必须转化为具象场景、人物动作、光影细节、视觉符号
- 严禁使用"氛围感""悲伤场景""画面感"等模糊无效描述

### 二、节奏控场
- 过渡/铺垫镜头：2-3秒，快切、平移、蒙太奇带过
- 核心情绪/关键剧情/主旨升华：3-6秒，慢推、定格、慢门强化
- 在【原文对照】开头标注建议时长，格式：(约 X 秒)

### 三、视觉统一
- 每个镜头必须包含唯一核心视觉焦点
- 遵循三分法、引导线、框架构图、对称构图等经典影视美学
- 杜绝畸形五官、扭曲肢体、模糊边缘、文字水印、多余杂物、画面噪点

## 角色与场景复用规范（关键）

已知资产库中的角色、场景、道具已提前生成参考图，必须严格复用，禁止自行发挥捏造。

角色列表：
{{characters}}

场景列表：
{{scenes}}

道具列表：
{{props}}

强制要求：
1. **人物引用规则**：角色图已提前生成，提示词中只需用【角色名】引用角色，**禁止写角色的穿着打扮、发型、外貌等具体描述**（这些信息已包含在角色参考图中）。只需描述角色在当前镜头中的动作、姿态、表情、位置关系。
2. **场景引用规则**：场景图已提前生成，提示词中只需用【场景名】引用场景，**禁止写场景的具体环境描述**（如建筑风格、布局、装饰等，这些信息已包含在场景参考图中）。只需描述当前镜头中的光影、时间、氛围变化。
3. 用【角色名】包裹角色名，例如：【张三】、【李四（少年形态）】
4. 用【场景名】包裹场景名，例如：【学校操场】、【老家客厅】
5. 用【道具名】包裹道具名，例如：【旧怀表】
6. 画风标记 `{{style_hint}}` 必须出现在每个提示词的第一句

## 输出格式（分隔符模式 · 唯一合法格式）

按下列分隔符约定输出，**禁止输出任何 JSON、引号包裹、字段名或 Markdown 围栏**：

- 开头标记：`_::-OUTPUT_START::-_`（单独一行）
- 记录分隔符：`_::-RECORD::-_`（单独一行，放在相邻两个分镜之间）
- 结尾标记：`_::-OUTPUT_END::-_`（单独一行）

每个分镜按下面 7 段顺序输出，禁止输出表格、列表、小标题或冗余字段：

【原文对照】
本镜对应的原始旁白文本，原封不动复制粘贴，含标点。开头标注建议时长：(约 X 秒)

出场人物：本镜在场的所有角色名，用顿号、分隔，每人后面括注身份/状态。必须从已知角色列表中选择，禁止编造。没有则填"无"。

【画面】把【原文对照】里的动作、环境、人物姿态转成可视化的画面描述，用陈述句，不含对白。出现角色/场景/道具时必须用【角色名】【场景名】【道具名】标记。注意：不写角色穿着打扮、不写场景具体环境，只写动作、姿态、表情、光影、氛围。

【首帧提示词】用于AI生成分镜首帧图片的完整提示词。第一句必须是画风({{style_hint}})。然后描述：景别、影视构图、角色动作姿态（不写穿着打扮）、场景光影氛围（不写具体环境）、运镜。纯视觉描述，不含对白。出现角色/场景/道具时必须用【角色名】【场景名】【道具名】标记。

【尾帧提示词】用于AI生成分镜尾帧图片的完整提示词。第一句必须是画风({{style_hint}})。与首帧形成递进对比（动作/表情/位置/光影变化）。然后描述：景别、影视构图、角色动作姿态（不写穿着打扮）、场景光影氛围（不写具体环境）。纯视觉描述，不含对白。出现角色/场景/道具时必须用【角色名】【场景名】【道具名】标记。

【视频提示词】用于AI生成首尾帧之间视频的完整提示词。第一句必须是画风({{style_hint}})。基于首尾帧画面基底，描述：专属运镜方式、人物动作变化（不写穿着打扮）、镜头运动幅度、环境动态变化（不写具体环境）、整体叙事节奏。不要重复旁白内容，只描述视觉运动。

【关联场景】本镜涉及的所有场景名，用顿号、分隔。必须从已知场景列表中选择，禁止编造。没有则填"无"。

## 输出示例

_::-OUTPUT_START::-_

_::-RECORD::-_

【原文对照】
(约 4 秒) 他站在老旧的火车站台，望着远去的列车，终于明白有些人一旦错过就是一生。

出场人物：张三

【画面】暮色黄昏，【火车站台】，暖黄路灯与冷蓝天空对比，【张三】孤独站立，背对镜头望向轨道尽头，远处列车尾灯微弱。

【首帧提示词】
{{style_hint}}，全景，三分法构图，【火车站台】，暮色黄昏，暖黄路灯与冷蓝天空对比，【张三】背对镜头孤独站立，望向轨道尽头，远处列车尾灯微弱，画面左侧站台立柱形成引导线

【尾帧提示词】
{{style_hint}}，中景，【火车站台】，天色渐暗，【张三】缓缓转身，侧脸被路灯照亮，表情沉默而释然，背景列车已消失只剩空旷轨道

【视频提示词】
{{style_hint}}，缓慢推镜头从全景推向【张三】背影，列车尾灯逐渐远去变小，镜头微微下沉，【张三】肩膀轻微颤动后缓缓转身，环境光从黄昏暖调过渡为夜晚冷调，整体节奏舒缓忧伤

【关联场景】火车站台

_::-OUTPUT_END::-_

## 待拆分剧本

{{script_text}}
""",
    },
]


# ============================================================
# 通用 CRUD
# ============================================================

def list_templates(
    session: Session,
    template_type: Optional[str] = None,
) -> list[PromptTemplate]:
    """查询模板列表，可按类型筛选。"""
    stmt = select(PromptTemplate)
    if template_type:
        stmt = stmt.where(PromptTemplate.template_type == template_type)
    stmt = stmt.order_by(PromptTemplate.template_type, PromptTemplate.sort_order, PromptTemplate.created_at)
    return list(session.exec(stmt).all())


def get_template(session: Session, template_id: str) -> Optional[PromptTemplate]:
    """获取单个模板。"""
    return session.get(PromptTemplate, template_id)


def get_default_template(session: Session, template_type: str) -> Optional[PromptTemplate]:
    """获取某类型的默认模板，没有默认则取该类型第一个模板。"""
    if template_type not in PROMPT_TEMPLATE_TYPES:
        raise ValueError(f"不支持的模板类型: {template_type}")

    default = session.exec(
        select(PromptTemplate)
        .where(PromptTemplate.template_type == template_type)
        .where(PromptTemplate.is_default == True)
        .order_by(PromptTemplate.sort_order)
    ).first()
    if default:
        return default

    return session.exec(
        select(PromptTemplate)
        .where(PromptTemplate.template_type == template_type)
        .order_by(PromptTemplate.sort_order)
    ).first()


def _clear_default_flag(session: Session, template_type: str, exclude_id: Optional[str] = None) -> None:
    """把同类型的其他模板默认标记取消。"""
    stmt = (
        select(PromptTemplate)
        .where(PromptTemplate.template_type == template_type)
        .where(PromptTemplate.is_default == True)
    )
    if exclude_id:
        stmt = stmt.where(PromptTemplate.id != exclude_id)
    for tmpl in session.exec(stmt).all():
        tmpl.is_default = False
        session.add(tmpl)


def create_template(session: Session, data: PromptTemplateCreate) -> PromptTemplate:
    """创建模板。"""
    if data.template_type not in PROMPT_TEMPLATE_TYPES:
        raise ValueError(f"不支持的模板类型: {data.template_type}")

    tmpl = PromptTemplate(**data.model_dump())
    if tmpl.is_default:
        _clear_default_flag(session, tmpl.template_type)
    session.add(tmpl)
    session.commit()
    session.refresh(tmpl)
    return tmpl


def update_template(
    session: Session,
    template_id: str,
    data: PromptTemplateUpdate,
) -> Optional[PromptTemplate]:
    """更新模板。"""
    tmpl = session.get(PromptTemplate, template_id)
    if not tmpl:
        return None
    if tmpl.is_builtin:
        # 内置模板只允许修改 content/description/sort_order/is_default，不允许改名称/类型
        allowed = {"content", "description", "sort_order", "is_default"}
        updates = data.model_dump(exclude_unset=True)
        for key in list(updates.keys()):
            if key not in allowed:
                raise ValueError(f"内置模板不允许修改字段: {key}")
    else:
        updates = data.model_dump(exclude_unset=True)

    if "template_type" in updates and updates["template_type"] not in PROMPT_TEMPLATE_TYPES:
        raise ValueError(f"不支持的模板类型: {updates['template_type']}")

    for key, value in updates.items():
        setattr(tmpl, key, value)

    if tmpl.is_default:
        _clear_default_flag(session, tmpl.template_type, exclude_id=tmpl.id)

    session.add(tmpl)
    session.commit()
    session.refresh(tmpl)
    return tmpl


def delete_template(session: Session, template_id: str) -> bool:
    """删除模板。内置模板不可删除。"""
    tmpl = session.get(PromptTemplate, template_id)
    if not tmpl or tmpl.is_builtin:
        return False
    session.delete(tmpl)
    session.commit()
    return True


# ============================================================
# 初始化内置模板
# ============================================================

def seed_builtin_templates(session: Session) -> int:
    """初始化内置模板。已存在同名同类型的内置模板则跳过。

    返回新增数量。
    """
    added = 0
    for data in BUILTIN_TEMPLATES:
        exists = session.exec(
            select(PromptTemplate)
            .where(PromptTemplate.template_type == data["template_type"])
            .where(PromptTemplate.is_builtin == True)
        ).first()
        if exists:
            continue

        # 如果该类型还没有任何模板，则把内置设为默认
        has_any = session.exec(
            select(PromptTemplate).where(PromptTemplate.template_type == data["template_type"])
        ).first()
        tmpl = PromptTemplate(
            name=data["name"],
            template_type=data["template_type"],
            description=data["description"],
            content=data["content"],
            is_default=not has_any,
            is_builtin=True,
            sort_order=data["sort_order"],
        )
        session.add(tmpl)
        added += 1

    if added:
        session.commit()
        logger.info(f"[prompt_templates] 已初始化 {added} 个内置模板")
    return added
