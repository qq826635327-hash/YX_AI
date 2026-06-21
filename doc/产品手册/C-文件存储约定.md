# C. 文件存储约定

> AI 修改涉及文件读写、路径处理的代码前，必须阅读本文档。
> 源码参考：`project_service.py`、`business_service.py`、`asset_service.py`、`execute_task.py`、`config.py`

---

## 1. 完整目录结构树

每个项目在磁盘上拥有一个独立的根目录，格式为 `{项目名}_{8位UUID}`（项目名经过 `_sanitize_name` 处理）。
默认根路径由 `config.yaml` 中 `storage.projects_root` 决定（默认 `../data/projects`，相对于 `backend/` 解析为绝对路径）。

```
data/projects/                          ← projects_root_abs（所有项目的父目录）
└── {sanitized_project_name}_{8位ID}/  ← 项目根目录（project.root_path）
    ├── script/                        ← 剧本文件（ScriptDocument）
    │
    ├── 角色/                          ← MODULE_DIR_MAP[Character] = "角色"
    │   └── {角色名}/                  ← sanitize_name(character.name)
    │       ├── images/                ← 角色图片（生成图、上传图）
    │       ├── videos/                ← 角色视频（预留）
    │       └── prompts/               ← 生成时的提示词记录（.txt）
    │
    ├── 场景/                          ← MODULE_DIR_MAP[Scene] = "场景"
    │   └── {场景名}/
    │       ├── images/
    │       ├── videos/
    │       └── prompts/
    │
    ├── 道具/                          ← MODULE_DIR_MAP[Prop] = "道具"
    │   └── {道具名}/
    │       ├── images/
    │       ├── videos/
    │       └── prompts/
    │
    ├── 分镜/                          ← MODULE_DIR_MAP[Shot] = "分镜"
    │   └── 第{N}集_{shot_no}/        ← 特殊命名，见第 6 节
    │       ├── images/                ← 首帧 / 末帧图片
    │       ├── videos/                ← 视频
    │       └── prompts/               ← 提示词记录
    │
    ├── assets/                        ← 通用素材（初始化时创建，兼容旧路径）
    │   ├── images/
    │   │   ├── characters/            ← 初始化预建（PROJECT_SUBDIRS）
    │   │   ├── scenes/
    │   │   ├── props/
    │   │   ├── first_frames/
    │   │   └── last_frames/
    │   ├── videos/
    │   │   └── shot_videos/
    │   └── uploads/                   ← 无目标实体的上传文件落盘处
    │
    ├── exports/                       ← 导出文件（预留）
    └── logs/                          ← 项目级日志（预留）
```

### 1.1 初始化时创建的目录（PROJECT_SUBDIRS）

项目创建时，`init_project_directory()` 会创建以下子目录：

```python
PROJECT_SUBDIRS = [
    "script",
    "assets/images/characters",
    "assets/images/scenes",
    "assets/images/props",
    "assets/images/first_frames",
    "assets/images/last_frames",
    "assets/videos/shot_videos",
    "assets/uploads",
    "exports",
    "logs",
]
```

> **注意**：`角色/`、`场景/`、`道具/`、`分镜/` 这四个模块目录**不在初始化时创建**，而是在第一个实体创建时由 `execute_task.py` 的 `target_dir.mkdir(parents=True, exist_ok=True)` 或上传时自动创建。

---

## 2. 目录命名规则

### 2.1 项目目录名（project_service._sanitize_name）

```python
def _sanitize_name(name: str) -> str:
    s = re.sub(r'[^\w\u4e00-\u9fff]', '_', name)  # 非中文/字母/数字/下划线 → _
    s = re.sub(r'_+', '_', s)                       # 合并多个下划线
    return s.strip('_')[:20]                         # 去首尾下划线，限制 20 字符
```

**示例**：

| 输入 | 输出 | 说明 |
|------|------|------|
| `我的新剧` | `我的新剧` | 纯中文，不变 |
| `Hello World` | `Hello_World` | 空格变下划线 |
| `Project #1!` | `Project_1` | 特殊字符替换 + 合并 |
| `___test___` | `test` | 首尾下划线被去除 |
| `这是一个非常非常非常非常长的项目名` | `这是一个非常非常非常非常长的项目名`（截断20字） | 超长截断 |

**项目文件夹最终格式**：`{sanitized_name}_{8位UUID}`

```
示例：我的新剧_a1b2c3d4
```

### 2.2 实体目录名（business_service.sanitize_name）

```python
def sanitize_name(name: str) -> str:
    for ch in ('/', '\\', ':', '*', '?', '"', '<', '>', '|'):
        name = name.replace(ch, '_')
    return name[:50] or "unknown"
```

与项目名的 `_sanitize_name` **不同**：
- 只替换 Windows 文件名禁用字符（10 个）
- 保留空格、特殊符号（如 `#`、`@`）
- 最大长度 50 字符（项目名限 20）
- 空名称返回 `"unknown"`

**示例**：

| 输入 | 输出 |
|------|------|
| `张三` | `张三` |
| `城堡/废墟` | `城堡_废墟` |
| `道具: 宝剑` | `道具_ 宝剑` |
| `""特殊""` | `__特殊__` |

### 2.3 分镜目录名（特殊规则）

分镜不使用 `sanitize_name(name)`，而是用 **集数 + 镜号** 的固定格式：

```
第{episode_no}集_{shot_no}
```

源码（`_compute_dirname`）：
```python
if model is Shot and session:
    ep = session.get(Episode, episode_id)
    return f"第{ep.episode_no}集_{shot_no}"
```

**示例**：

| 集数 | 镜号 | 目录名 |
|------|------|--------|
| 1 | 1 | `第1集_1` |
| 1 | 15 | `第1集_15` |
| 3 | 7 | `第3集_7` |

> `shot_no` 是数字，不带前导零。格式解析正则：`r"第(\d+)集[_\s](.+)"`

---

## 3. 创建 / 重命名 / 删除时的磁盘操作

### 3.1 创建

| 操作 | 磁盘行为 | 源码位置 |
|------|---------|---------|
| 新建项目 | `mkdir -p` 创建项目根目录 + `PROJECT_SUBDIRS` | `project_service.init_project_directory()` |
| 新建角色/场景/道具 | **不主动创建目录**。首次生成图片或上传时，`target_dir.mkdir(parents=True, exist_ok=True)` 按需创建 | `execute_task.py` / `asset_service.save_uploaded_file()` |
| 新建分镜 | 同上，首次生成时按需创建 `分镜/第N集_M/images/` | `execute_task.py` |

### 3.2 重命名

当实体（角色/场景/道具）的 `name` 字段被修改时，`update_entity()` 触发以下流程：

```
1. 计算旧目录名 old_dirname = _compute_dirname(model, entity_before_update)
2. 应用新字段到内存中的 entity
3. 计算新目录名 new_dirname = _compute_dirname(model, entity_after_update)
4. 若 old_dirname != new_dirname → 调用 _rename_entity_dir()
   a. 用 os.replace() 原子重命名磁盘目录
   b. 查找所有关联 Asset，更新 file_path（旧前缀 → 新前缀）
5. 统一 commit（实体改名 + Asset 路径更新在同一事务）
```

**关键细节**：
- 使用 `os.replace()` 而非 `Path.rename()`，因为同文件系统下 `os.replace()` 是原子操作
- `auto_commit=False` 时 Asset 路径更新暂存但不 commit，由调用方统一 commit，保证事务原子性
- 磁盘重命名失败只记日志，不回滚 DB（best-effort 策略）

**示例**：角色 "张三" 改名为 "李四"

```
磁盘操作：角色/张三/ → 角色/李四/
Asset.file_path 更新：
  角色/张三/images/gen_1718900000_a1b2c3d4.png → 角色/李四/images/gen_1718900000_a1b2c3d4.png
```

### 3.3 删除

删除实体时（`delete_entity()`），磁盘清理流程：

```
1. 收集关联 Asset（通过 target_type + target_id 查询）
2. 逐个删除 Asset：
   a. 清除所有外键引用（Character.image_asset_id, Shot.first_frame_asset_id 等 → None）
   b. commit 外键清理
   c. 物理删除文件（resolve_asset_path → unlink）
   d. 同步删除对应的 prompt 文件（images/xxx.png → prompts/xxx.txt）
   e. commit 删除 Asset 记录
3. rmtree 实体目录（兜底清理）
4. 删除实体 DB 记录
5. 更新项目统计数据
```

**安全机制**：
- 物理文件删除放在独立 `try-except` 中，`PermissionError`（文件被占用）只记日志不抛异常
- 项目删除时有路径安全校验：`root.is_relative_to(projects_root)` 防止误删系统目录
- `shutil.rmtree(root, ignore_errors=True)` 容错删除

---

## 4. Asset 的 file_path 格式约定

### 4.1 格式

`Asset.file_path` 存储的是**相对于项目根目录的路径**，使用**正斜杠 `/`** 作为分隔符（即使在 Windows 上）。

```python
# execute_task.py 中的转换：
file_path_rel = str(output_path.relative_to(project_root.resolve())).replace("\\", "/")
```

### 4.2 示例

```
角色/张三/images/gen_1718900000_a1b2c3d4.png
角色/张三/images/1718900000_upload.png        ← 上传的文件
角色/张三/prompts/gen_1718900000_a1b2c3d4.txt ← 提示词记录
分镜/第1集_5/images/gen_1718900000_c3d4e5f6.png
分镜/第1集_5/videos/gen_1718900000_c3d4e5f6.mp4
assets/uploads/1718900000_misc_file.png        ← 无目标实体的上传
```

### 4.3 路径解析（resolve_asset_path）

```python
def resolve_asset_path(project_root: Path, file_path: str) -> Path:
```

- **禁止绝对路径**：如果传入绝对路径，会尝试转换为相对路径
- **防路径穿越**：二次校验 `resolved.is_relative_to(project_root.resolve())`
- 非法路径直接 `raise ValueError`

### 4.4 上传文件命名

```python
safe_name = f"{int(time.time())}_{original_filename}"
```

上传文件加 Unix 时间戳前缀避免重名。文件名经过 `_sanitize_filename()` 处理：
- 取纯文件名（`Path(filename).name`）防止路径穿越
- 替换 `/` 和 `\` 为 `_`
- 防止 `.` 开头的隐藏文件

---

## 5. 任务生成后的文件保存路径

生成任务（`execute_task.py`）的文件保存规则：

### 5.1 目录计算

```python
entity_name = get_entity_dirname(session, target_type, target_id) or target_id[:8]
module_dir  = TARGET_TYPE_DIR_MAP.get(target_type, "其他")
```

### 5.2 完整路径规则

| target_type | 模块目录 | 实体目录 | 子目录 | 扩展名 | 完整路径示例 |
|-------------|---------|---------|--------|--------|-------------|
| `character` | `角色` | `sanitize_name(name)` | `images` | `.png` | `角色/张三/images/gen_1718900000_a1b2c3d4.png` |
| `scene` | `场景` | `sanitize_name(name)` | `images` | `.png` | `场景/城堡/images/gen_1718900000_a1b2c3d4.png` |
| `prop` | `道具` | `sanitize_name(name)` | `images` | `.png` | `道具/宝剑/images/gen_1718900000_a1b2c3d4.png` |
| `shot_first_frame` | `分镜` | `第N集_M` | `images` | `.png` | `分镜/第1集_5/images/gen_1718900000_a1b2c3d4.png` |
| `shot_last_frame` | `分镜` | `第N集_M` | `images` | `.png` | `分镜/第1集_5/images/gen_1718900000_a1b2c3d4.png` |
| `shot_video` | `分镜` | `第N集_M` | `videos` | `.mp4` | `分镜/第1集_5/videos/gen_1718900000_a1b2c3d4.mp4` |

### 5.3 文件名格式

```python
base_name = f"gen_{int(time.time())}_{task_id[:8]}"
file_name = base_name + ext
```

**示例**：`gen_1718900000_a1b2c3d4.png`

如果同名文件已存在，自动加序号：
```python
# 防重名：gen_1718900000_a1b2c3d4_1.png, gen_1718900000_a1b2c3d4_2.png ...
```

### 5.4 提示词文件（可选）

当 `config.yaml` 中 `tasks.save_prompts = true` 时（默认开启），生成的提示词保存为 `.txt` 文件：

```
路径：{module_dir}/{entity_name}/prompts/{image_stem}.txt
示例：角色/张三/prompts/gen_1718900000_a1b2c3d4.txt
```

内容格式：
```
Prompt: {提示词文本}
Size: {尺寸}
Asset Type: image
Task ID: {task_id}
Generated at: {ISO 8601 时间戳}
```

### 5.5 多图片输出

如果 API 返回多张图片，第一张按正常命名，后续加下标：

```
gen_1718900000_a1b2c3d4.png    ← 第 1 张（主输出，创建 Asset 记录）
gen_1718900000_a1b2c3d4_1.png  ← 第 2 张
gen_1718900000_a1b2c3d4_2.png  ← 第 3 张
```

> 只有第一张图片会创建 Asset 记录并回填到实体。

---

## 6. 分镜目录的特殊命名规则

### 6.1 命名格式

```
第{episode_no}集_{shot_no}
```

- `episode_no`：来自 `Episode.episode_no` 字段（整数）
- `shot_no`：来自 `Shot.shot_no` 字段（整数）
- 中间用下划线 `_` 连接

### 6.2 解析规则

同步时通过正则解析目录名：

```python
m = re.match(r"第(\d+)集[_\s](.+)", dirname)
ep_no = int(m.group(1))       # 集数
shot_no_str = m.group(2)      # 镜号部分（可能是 "S01" 或纯数字）
```

镜号提取：
```python
num_match = re.search(r"\d+", shot_no_str)
shot_no_num = int(num_match.group())
```

### 6.3 分镜的 target_type 分支

分镜有三种素材类型，对应不同的 `target_type`：

| target_type | 含义 | 存储子目录 | Asset 回填字段 |
|-------------|------|-----------|---------------|
| `shot_first_frame` | 首帧图片 | `分镜/第N集_M/images/` | `Shot.first_frame_asset_id` |
| `shot_last_frame` | 末帧图片 | `分镜/第N集_M/images/` | `Shot.last_frame_asset_id` |
| `shot_video` | 视频 | `分镜/第N集_M/videos/` | `Shot.video_asset_id` |

---

## 7. 同步机制

### 7.1 触发方式

通过 `sync_assets(session, project_id)` 函数调用（对应 API 端点）。

### 7.2 双向同步流程

**阶段 1：清理（DB → 磁盘方向）**

```
遍历项目中所有 Asset 记录：
  → resolve_asset_path() 计算绝对路径
  → 如果文件不存在 → 删除该 Asset 记录（delete_file=False）
```

**阶段 2：发现（磁盘 → DB 方向）**

```
1. 收集 DB 中所有 file_path（统一为 / 分隔符）
2. 扫描角色/场景/道具目录下的每个实体目录：
   → 遍历 images/ 和 videos/ 子目录
   → 检查扩展名（.png .jpg .jpeg .webp .bmp .gif .tiff / .mp4 .webm .mov .mkv .avi）
   → 如果文件不在 DB 中 → 创建 Asset 记录
   → 如果实体没有主图（image_asset_id 为空）→ 自动回填
3. 扫描分镜目录（同样的逻辑，但 target_type 推断规则不同）：
   → 文件名含 "last" 或 "末帧" → shot_last_frame
   → 文件名含 "video" 或 "视频" 或在 videos/ 目录 → shot_video
   → 其他 → shot_first_frame
   → 自动回填到 Shot 的对应字段
```

### 7.3 返回结果

```python
{
    "checked": 42,       # 检查的 DB 记录数
    "cleaned": 3,        # 清理的丢失文件记录数
    "discovered": 5,     # 新发现并注册的文件数
    "errors": 0,         # 处理时出错的记录数
    "details": [...]     # 每条变更的详情
}
```

### 7.4 同步时的目录名匹配

同步通过目录名反查实体：
- **角色/场景/道具**：对每个目录名调用 `sanitize_name(entity.name)` 与目录名比较
- **分镜**：解析 `第N集_M` 格式，通过 `episode_no` 找到 `Episode`，再通过 `shot_no` 找到 `Shot`

---

## 8. 安全注意事项

1. **路径穿越防护**：所有路径解析都经过 `resolve_asset_path()` 二次校验
2. **项目删除校验**：`root.is_relative_to(projects_root)` 防止删除项目目录外的文件
3. **文件名清洗**：上传文件用 `_sanitize_filename()` 处理，防止路径注入
4. **文件大小限制**：上传默认上限 200MB（`save_uploaded_file` 的 `max_size` 参数）
5. **文件类型白名单**：`config.yaml` 中 `storage.allowed_image_types` 和 `storage.allowed_video_types`
6. **Windows 兼容**：所有路径存储为 `/` 分隔符，`os.replace()` 在同文件系统下保证原子性

---

## AI 开发检查清单

> AI 修改文件存储相关代码时，必须执行以下检查。

- [ ] 已阅读本文档，了解目录命名规则
- [ ] 新增路径操作使用 `resolve_asset_path()` 做安全校验
- [ ] 新增目录创建使用 `mkdir(parents=True, exist_ok=True)`
- [ ] 文件名使用 `sanitize_name()` 或 `_sanitize_filename()` 处理
- [ ] Asset.file_path 使用正斜杠 `/` 分隔
- [ ] 删除操作考虑了文件被占用（`PermissionError`）的情况
- [ ] `doc/开发手册/CHANGELOG.md` 已更新
