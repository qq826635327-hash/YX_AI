# 04 · 通用 CRUD 模式

> 角色/场景/道具/剧集/分镜——5 个高度相似的实体如何避免 1000 行重复代码。

## 1. 为什么统一抽象

这 5 个实体的表结构惊人相似：

| 字段 | Character | Scene | Prop | Episode | Shot |
| --- | --- | --- | --- | --- | --- |
| id | ✓ | ✓ | ✓ | ✓ | ✓ |
| project_id | ✓ | ✓ | ✓ | ✓ | ✓ |
| name | ✓ | ✓ | ✓ | title | summary/shot_no |
| description | ✓ | ✓ | ✓ | ✓ | ✓ |
| settings | ✓ | ✓ | ✓ | — | — |
| gen_status | ✓ | ✓ | ✓ | — | — (用 per_frame) |
| image_asset_id | ✓ | ✓ | ✓ | — | — |
| sort_order | ✓ | ✓ | ✓ | ✓ | ✓ |
| 外键 | — | — | — | project | episode + project |

**2026-06-20 之前**：每个实体一个 Service 类（`CharacterService`、`SceneService`、`PropService`、`EpisodeService`、`ShotService`），共 1000+ 行高度相似的代码。

**2026-06-20 之后**：删除 5 个 Service 类，全部走 `business_service.py` 的 4 个通用函数。

## 2. 通用 CRUD API

文件：`backend/app/services/business_service.py`

```python
def list_by_project(session, model, project_id, order_field="sort_order") -> List[T]
def get_one(session, model, entity_id) -> Optional[T]
def create_entity(session, model, project_id, data: dict) -> T
def update_entity(session, model, entity_id, data: dict) -> Optional[T]
def delete_entity(session, model, entity_id) -> bool
```

### 实体目录名计算（统一入口）

```python
from app.services.business_service import sanitize_name, get_entity_dirname, TARGET_TYPE_DIR_MAP

# 清洗实体名称用于目录名
dirname = sanitize_name("角色/名称")  # → "角色_名称"

# 根据 target_type + target_id 计算磁盘目录名
dirname = get_entity_dirname(session, "character", "uuid-xxx")  # → "角色名"
dirname = get_entity_dirname(session, "shot_first_frame", "uuid-xxx")  # → "第1集_S01"

# 模块目录映射
module_dir = TARGET_TYPE_DIR_MAP["character"]  # → "角色"
```

> ⚠️ `sanitize_name`、`get_entity_dirname`、`TARGET_TYPE_DIR_MAP` 是**唯一**的实体目录名计算入口。`execute_task.py`、`asset_service.py` 等都引用这些函数，**不要**在其他地方重新实现类似逻辑。

### 用法示例

```python
# api/characters.py
from app.services.business_service import (
    list_by_project, get_one, create_entity, update_entity, delete_entity,
)
from app.models import Character

@router.get("/projects/{project_id}/characters")
def list_characters(project_id: str, session: Session = Depends(get_session)):
    items = list_by_project(session, Character, project_id)
    return {"data": serialize_models(items)}

@router.post("/projects/{project_id}/characters")
def create_character(project_id: str, body: CharacterCreate, session: Session = Depends(get_session)):
    entity = create_entity(session, Character, project_id, body.model_dump(exclude_unset=True))
    return {"data": serialize_model(entity)}

@router.delete("/characters/{character_id}")
def delete_character(character_id: str, session: Session = Depends(get_session)):
    success = delete_entity(session, Character, character_id)
    if not success:
        raise HTTPException(404, "角色不存在")
    return {"data": {"id": character_id}}
```

## 3. `update_entity` 的关键逻辑

更新实体时**同步重命名磁盘目录**：

1. **更新前**：用 `_compute_dirname(model, entity, session)` 计算旧目录名
2. **更新 DB 字段**：`setattr` + `commit`
3. **更新后**：用 `_compute_dirname` 计算新目录名
4. **目录名变化** → 调用 `_rename_entity_dir()`：
   - 磁盘目录重命名（`old_dir.rename(new_dir)`）
   - 更新关联 Asset 的 `file_path`（替换路径前缀，如 `角色/旧名/` → `角色/新名/`）

```python
# _compute_dirname 根据实体类型计算目录名
# 角色/场景/道具：sanitize_name(name)
# 分镜：f"第{ep.episode_no}集_{shot.shot_no}"（需查关联 Episode）
```

> ⚠️ 分镜目录名依赖 `episode_no`（来自关联 Episode）和 `shot_no`。当 `shot_no` 变更时，`update_entity` 自动处理；当 `episode_no` 变更时，由 `api/episodes.py` 的 `_rename_shots_dirs()` 批量处理该剧集下所有分镜目录。

## 4. `delete_entity` 的关键逻辑

删除实体时**同步清理**：

1. **关联的 Asset 记录**（按 `target_type + target_id` 查）
2. **角色/场景/道具的 `image_asset_id`**（兜底）
3. **Asset 的物理文件**（调 `asset_service.delete_asset(delete_file=True)`）
4. **实体目录**（`shutil.rmtree(.../module_dir/<entity_name>)`）
5. **项目统计**（`update_project_stats` 重算 `character_count` 等）

> ⚠️ 这是最容易出 Bug 的地方。文件删除用 `ignore_errors=True`，文件锁/PermissionError 不会让整个删除失败。

## 5. 分镜特殊处理

分镜（Shot）属于剧集（Episode），所以多两个函数：

```python
def list_shots_by_episode(session, episode_id) -> List[Shot]
def create_shot(session, episode_id, project_id, data: dict) -> Shot
```

`list_shots_by_episode` 按 `sort_order, shot_no` 排序。

## 6. 前端通用 CRUD

文件：`frontend/src/hooks/useBusiness.ts`

```typescript
export function useEntities<T>(projectId: string, type: EntityType) {
  return useQuery({
    queryKey: ["business", type, projectId],
    queryFn: () => businessApi.list<T>(type, projectId).then(d => d.data),
  });
}

export function useCreateEntity<T>(projectId: string, type: EntityType) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => businessApi.create<T>(type, projectId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["business", type, projectId] });
      qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}
```

## 7. 何时打破抽象：例外情况

如果你要加的实体**有以下任一情况**，建议自己写 Service 而不是用通用函数：

- 有大量**关联**逻辑（不只是单层 image_asset_id，而是 N:M 多对多）
- 有**复杂的状态机**（不是简单的 `gen_status`）
- 有**特殊的文件结构**（比如多文件 + 子目录）
- 需要**事务性**（多步操作要么都成功要么都回滚）

## 8. 加新业务实体的清单

比如要加 "标签（Tag）"：

1. `backend/app/models/tag.py`：定义 `Tag(SQLModel, table=True)`，字段 `id, project_id, name, color, created_at, updated_at`
2. `backend/app/models/__init__.py`：导出
3. `backend/app/api/tags.py`：路由，**用通用 CRUD**（不需要新 Service）
4. `backend/app/api/__init__.py`：包含路由
5. `frontend/src/types/index.ts`：加类型
6. `frontend/src/api/business.ts`：如果是简单 CRUD，**扩展 entityConfig**；如果复杂，加 `tagsApi`
7. `frontend/src/hooks/useBusiness.ts`：或加 `useTags`
8. `frontend/src/pages/TagsPage.tsx`：页面（参考 CharactersPage）
9. `frontend/src/App.tsx`：加路由
10. `frontend/src/components/layout/Sidebar.tsx`：加菜单
11. 同步 `doc/产品手册/A-完整路由表.md` 和 `08-通用资产卡片.md`（如适用）

---

## AI 测试检查点

修改通用 CRUD 逻辑后，必须验证以下场景：

### create_entity 测试
```powershell
# 验证创建后的数据完整性
curl -X POST http://127.0.0.1:8000/api/projects/{pid}/characters \
  -H "Content-Type: application/json" \
  -d '{"name": "测试角色", "char_type": "protagonist", "description": "描述"}'
# 期望：200，返回完整实体数据
```

### update_entity 测试（含目录重命名）
```powershell
# 重命名后验证目录同步
curl -X PATCH http://127.0.0.1:8000/api/projects/{pid}/characters/{cid} \
  -H "Content-Type: application/json" \
  -d '{"name": "新名字"}'
# 期望：200，磁盘目录同步更新，Asset file_path 同步更新
```

### delete_entity 测试
```powershell
# 删除后验证级联清理
curl -X DELETE http://127.0.0.1:8000/api/projects/{pid}/characters/{cid}
# 期望：200，磁盘目录清理，Asset 记录清理
```

### 自动化测试命令
```powershell
cd D:\影序AI\backend
.venv\Scripts\python.exe -m pytest tests/api/test_characters.py tests/api/test_scenes.py tests/api/test_props.py -v --tb=short
```
