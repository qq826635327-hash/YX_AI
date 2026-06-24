# 04 IPC 接口全表

> 全部 82 个 IPC 通道（来自 `out/main/index.cjs` 的 `ipcMain.handle` 列表），按 preload 暴露的命名空间分组。所有方法均通过 `window.electronAPI.<ns>.<method>(...)` 访问。

## 1. fs（文件系统，14 通道）

| 通道 | preload 方法 | 说明 |
| --- | --- | --- |
| `fs:read-file` | `readFile(path)` | 读 utf-8 文本 |
| `fs:write-file` | `writeFile(path, content)` | 写 utf-8 文本 |
| `fs:write-file-binary` | `writeFileBinary(path, base64)` | 写 base64 解码后的二进制 |
| `fs:read-file-binary` | `readFileBinary(path)` | 读 → base64 |
| `fs:delete-file` | `deleteFile(path)` | 删文件 |
| `fs:remove-dir` | `removeDir(path)` | 递归删目录 |
| `fs:exists` | `exists(path)` | 是否存在 |
| `fs:readdir` | `readdir(path)` | 列表 + stat |
| `fs:mkdir` | `mkdir(path)` | 递归创建 |
| `fs:rename` | `rename(from, to)` | 重命名 / 移动 |
| `fs:read-dir-names` | `readDirNames(path)` | 仅文件名 |
| `fs:stat` | `stat(path)` | stat 信息 |
| `fs:copy-file` | `copyFile(from, to)` | 单文件复制 |
| `fs:copy-dir` | `copyDir(from, to)` | 递归复制 |
| `fs:glob-canvas-files` | `globCanvasFiles(root, opts?)` | 扫描 `*.canvas.json` |
| `fs:write-builtin-template-zip` | `writeBuiltinTemplate(slug, base64)` | 仅 dev 模式：把工作流 zip 写进 `src/lib/comfy/builtin-workflows/registry/<slug>.wlmj-workflow.zip` |
| `fs:validate-project-dir` | `validateProjectDir(path)` | 预校验目录是否可写 |

## 2. dialog（原生对话框，2）

| 通道 | 方法 |
| --- | --- |
| `dialog:open-directory` | `openDirectory()` |
| `dialog:save-file` | `saveFile(options)` |

## 3. shell（系统能力，2）

| 通道 | 方法 |
| --- | --- |
| `shell:open-external` | `openExternal(url)` |
| `shell:open-path` | `openPath(path)` |

## 4. storage / system / fingerprint / app / window / clipboard / zoom

```ts
window.electronAPI.storage.getBasePath()              // userData/data
window.electronAPI.system.getInfo()                  // { platform, home, appData, env }
window.electronAPI.fingerprint.get()                  // 同步：硬件指纹
window.electronAPI.fingerprint.diag()                 // 异步：各组件状态
window.electronAPI.app.getVersion()
window.electronAPI.app.getArch()
window.electronAPI.app.isPackaged()
window.electronAPI.app.openNewWindow(route)
window.electronAPI.app.getDefaultProjectDir()         // 文档/1人漫剧/projects
window.electronAPI.window.minimize()
window.electronAPI.window.maximize()
window.electronAPI.window.close()
window.electronAPI.window.isMaximized()
window.electronAPI.window.onMaximizeChange(cb)        // → unsubscribe
window.electronAPI.clipboard.copyImage(base64PNG)
window.electronAPI.zoom.setFactor(factor)
window.electronAPI.zoom.getFactor()
```

## 5. directoryWatcher

```ts
window.electronAPI.directoryWatcher.startWatch(dirPath)
window.electronAPI.directoryWatcher.stopWatch(dirPath)
window.electronAPI.directoryWatcher.onFilesChanged(cb) // payload: { dirPath, files: string[] }
```

监听 `角色/`、`场景/`、`道具/`、`剧集/`、`分镜/`、`project.json`。

## 6. logger / projectLog

```ts
window.electronAPI.logger.append(level, args)         // send
window.electronAPI.logger.getDir()
window.electronAPI.logger.openDir()
window.electronAPI.projectLog.append(projectRoot, lines) // 写到 <root>/日志/
```

## 7. net（HTTP 出站，3）

```ts
window.electronAPI.net.fetchJson(url, { headers?, timeoutMs? })
window.electronAPI.net.fetchText(url, { headers?, timeoutMs? })
window.electronAPI.net.fetchBinary(url, { headers?, timeoutMs? })  // → ArrayBuffer
```

主进程实现包含：协议校验、重定向（最多 5 次）、超时 8s/12s/120s。

## 8. outbound（统一出站 AI 请求，7）

```ts
window.electronAPI.outbound.request({
  providerId, model, kind: "text"|"image"|"video"|"audio",
  messages|inputs|prompt, images?, params?, stream: bool
})
// 返回 { ok, data|error, token? }  ；流式走 outbound:event
window.electronAPI.outbound.registerSecrets(providerId, secrets)
window.electronAPI.outbound.clearSecrets(providerId)
window.electronAPI.outbound.clearAllSecrets()
window.electronAPI.outbound.cancel(token)
window.electronAPI.outbound.setChunkBroadcast(enabled)  // 控制流式 chunk 是否推到 renderer
window.electronAPI.outbound.setDefaults({ timeoutMs?, retry? }) // 用户在通用设置里改
```

事件：

- `outbound:event` — `{ token, type: "chunk"|"done"|"error", payload }`

## 9. volc（火山方舟，8）

```ts
window.electronAPI.volc.getSummary()                    // 不返回 SK 明文
window.electronAPI.volc.saveCredentials({ accessKeyId, secretAccessKey, region? })
window.electronAPI.volc.clearCredentials()
window.electronAPI.volc.testCredentials(input)         // 一次性 ListAssets
window.electronAPI.volc.listAssets({ groupType?, pageNumber, pageSize })  // AIGC / LivenessFace
window.electronAPI.volc.fetchAssetBytes(url)           // 解决 CDN CORS
window.electronAPI.volc.revealCredentials()             // 用户点"眼睛"图标才调用
```

## 10. mediaMeta（媒体水印，3）

```ts
window.electronAPI.mediaMeta.embed({ bytes: ArrayBuffer, meta: WlmjMediaMeta })
window.electronAPI.mediaMeta.read({ bytes: ArrayBuffer })   // → metas[]
window.electronAPI.mediaMeta.readByKind({ bytes, kind })    // → meta|null
```

## 11. mediaProtocol

```ts
window.electronAPI.mediaProtocol.setAllowedRoots([absPath, ...]) // 注册可被 app:// 协议代理的目录
```

## 12. pluginHost（13）

```ts
window.electronAPI.pluginHost.status()
window.electronAPI.pluginHost.ensureReady()
window.electronAPI.pluginHost.restart()
window.electronAPI.pluginHost.call(method, params, opts?)
window.electronAPI.pluginHost.onEvent(cb)                    // Host 推事件
window.electronAPI.pluginHost.onUploadRequest(cb)            // uploadToOSS 请求
window.electronAPI.pluginHost.resolveUploadRequest(id, payload)
window.electronAPI.pluginHost.onUploadToPublicUrlRequest(cb) // uploadToPublicUrl 请求
window.electronAPI.pluginHost.resolveUploadToPublicUrlRequest(id, payload)
```

事件：

- `pluginHost:event` `{ type, payload }`
- `pluginHost:upload-request` `{ requestId, dataUrl, category }`
- `pluginHost:upload-to-public-url-request` `{ requestId, dataUrl, category, zhongzhuanAuth? }`

## 13. claudeAgent（15）

```ts
window.electronAPI.claudeAgent.start({ prompt, workdir?, autoConfirm?, skillIds? })
window.electronAPI.claudeAgent.cancel(turnId)
window.electronAPI.claudeAgent.respondPermission(permissionId, decision)
window.electronAPI.claudeAgent.setAutoConfirm(bool)
window.electronAPI.claudeAgent.getStatus()
window.electronAPI.claudeAgent.testConnection({ apiKey, baseUrl, model })
window.electronAPI.claudeAgent.listSessions(dir)
window.electronAPI.claudeAgent.getSessionMessages(sessionId, dir)
window.electronAPI.claudeAgent.deleteSession(sessionId, dir)
window.electronAPI.claudeAgent.rewindSession(sessionId, dir, userPromptIndex)
window.electronAPI.claudeAgent.listCustomSkills()           // userData/claude-skills
window.electronAPI.claudeAgent.saveCustomSkill(skill, create)
window.electronAPI.claudeAgent.deleteCustomSkill(id)
window.electronAPI.claudeAgent.getCustomSkillsDir()
window.electronAPI.claudeAgent.getBuiltinSkillBodies()      // 内置 Skill 的 markdown 正文
window.electronAPI.claudeAgent.revealCustomSkills()         // shell.openPath
window.electronAPI.claudeAgent.onEvent(cb)                  // Agent 流式事件
```

事件：

- `claudeAgent:event` `{ type, ... }`，type ∈ `message_start / content_block_delta / content_block_stop / tool_use / tool_result / permission_request / result / error / end`

## 14. 错误码

```ts
const RpcErrorCodes = {
  ParseError: -32700,
  InvalidRequest: -32600,
  MethodNotFound: -32601,
  InvalidParams: -32602,
  InternalError: -32603,
  Cancelled: -32800,
  Timeout: -32801,
  NetworkError: -32802,
  AuthError: -32803,
  QuotaExceeded: -32804,
  UpstreamError: -32810,
};
```

---

**下一步**：阅读 `10-首页与项目管理.md`。
