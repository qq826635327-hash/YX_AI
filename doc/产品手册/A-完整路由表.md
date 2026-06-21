# 附录 A：完整路由表

## A.1 前端路由

| 路由 | 页面 | 描述 |
|------|------|------|
| `/` | HomePage | 首页/项目列表 |
| `/projects/:id` | ProjectDetailPage | 项目总览 |
| `/projects/:id/script` | ScriptPage | 剧本 |
| `/projects/:id/characters` | CharactersPage | 角色列表 |
| `/projects/:id/characters/:cid` | CharacterDetailPage | 角色详情 |
| `/projects/:id/scenes` | ScenesPage | 场景列表 |
| `/projects/:id/scenes/:sid` | SceneDetailPage | 场景详情 |
| `/projects/:id/props` | PropsPage | 道具列表 |
| `/projects/:id/props/:pid` | PropDetailPage | 道具详情 |
| `/projects/:id/episodes` | EpisodesPage | 剧集结构 |
| `/tasks` | TasksPage | 任务中心-当前项目 |
| `/tasks/all` | TasksAllPage | 任务中心-全部 |
| `/settings/api` | SettingsApiPage | API 供应商 |
| `/settings/plugins` | SettingsPluginsPage | 插件扩展 |
| `/settings/models` | SettingsModelsPage | 模型配置 |
| `/settings/prompts` | SettingsPromptsPage | 提示词模版 |
| `/settings/comfyui-servers` | SettingsComfyuiServersPage | ComfyUI 服务器 |
| `/settings/comfyui-workflows` | SettingsComfyuiWorkflowsPage | ComfyUI 工作流 |

## A.2 侧边栏菜单结构

### 项目内容（进入项目后）
```
├── 剧本
├── 角色
├── 场景
├── 道具
└── 剧集结构
```

### 任务中心
```
├── 当前项目
└── 全部项目
```

### 配置中心
```
├── API 供应商
├── 插件扩展
├── 模型配置
├── 提示词模版
├── ComfyUI 服务器
└── ComfyUI 工作流
```

## A.3 后端 API 分类

### 项目管理
| 方法 | 路径 |
|------|------|
| GET | `/api/projects` |
| POST | `/api/projects` |
| GET | `/api/projects/{id}` |
| PATCH | `/api/projects/{id}` |
| DELETE | `/api/projects/{id}` |

### 剧本
| 方法 | 路径 |
|------|------|
| GET | `/api/projects/{id}/script` |
| PUT | `/api/projects/{id}/script` |
| POST | `/api/projects/{id}/script/parse` |

### 角色 / 场景 / 道具 / 剧集
统一模式：
| 方法 | 路径 |
|------|------|
| GET | `/api/projects/{id}/{entities}` |
| POST | `/api/projects/{id}/{entities}` |
| GET | `/api/projects/{id}/{entities}/{eid}` |
| PATCH | `/api/projects/{id}/{entities}/{eid}` |
| DELETE | `/api/projects/{id}/{entities}/{eid}` |

### 分镜
| 方法 | 路径 |
|------|------|
| GET | `/api/episodes/{eid}/shots` |
| POST | `/api/episodes/{eid}/shots` |
| GET | `/api/shots/{sid}` |
| PATCH | `/api/shots/{sid}` |
| DELETE | `/api/shots/{sid}` |
| GET | `/api/shots/{sid}/references` |
| POST | `/api/shots/{sid}/{characters|scenes|props}` |
| DELETE | `/api/shots/{sid}/{characters|scenes|props}/{id}` |

### 素材
| 方法 | 路径 |
|------|------|
| GET | `/api/assets` |
| GET | `/api/assets/{id}` |
| GET | `/api/assets/{id}/file` |
| POST | `/api/assets/{id}/upload` |
| POST | `/api/assets/projects/{id}/upload` |
| DELETE | `/api/assets/{id}` |
| POST | `/api/assets/sync` |

### 任务
| 方法 | 路径 |
|------|------|
| GET | `/api/tasks` |
| GET | `/api/tasks/{id}` |

### 生成
| 方法 | 路径 |
|------|------|
| POST | `/api/generate` |
| POST | `/api/generate/batch` |
| POST | `/api/generate/{id}/retry` |
| POST | `/api/generate/{id}/cancel` |

### 配置（Settings API）
| 方法 | 路径 |
|------|------|
| GET | `/api/config/system` |
| GET | `/api/config/comfyui` |
| PATCH | `/api/config/llm` |

### Provider（供应商 API，前缀 `/api/config/providers`）
| 方法 | 路径 |
|------|------|
| GET | `/api/config/providers` |
| POST | `/api/config/providers` |
| GET | `/api/config/providers/{id}` |
| PATCH | `/api/config/providers/{id}` |
| DELETE | `/api/config/providers/{id}` |
| POST | `/api/config/providers/{id}/test` |

### Workflow（工作流 API，前缀 `/api/config/workflows`）
| 方法 | 路径 |
|------|------|
| GET | `/api/config/workflows` |
| POST | `/api/config/workflows` |
| GET | `/api/config/workflows/{id}` |
| PATCH | `/api/config/workflows/{id}` |
| DELETE | `/api/config/workflows/{id}` |

### 日志
| 方法 | 路径 |
|------|------|
| GET | `/api/logs` |
| GET | `/api/logs/info` |
| POST | `/api/logs/clear` |

## A.4 WebSocket 通道

| 通道 | 说明 |
|------|------|
| `/ws/tasks` | 任务进度实时推送 |
| `/ws/script` | 剧本解析进度推送 |
| `/ws/logs` | 后端日志实时推送 |

---

## AI 开发检查清单

> AI 修改本模块时，必须执行以下检查。

- [ ] 已阅读 `doc/开发手册/08-常见Bug与注意事项.md`
- [ ] 后端改动：Python 语法检查通过 + pytest 全部通过
- [ ] 前端改动：`npx tsc --noEmit` 无错误
- [ ] `doc/开发手册/CHANGELOG.md` 已更新
- [ ] 本文件已更新（如产品行为有变化）
