# 34 统一公共 URL 上传

> 插件场景里，dataURL（base64）需要变成"可被外部访问的 URL"，供 AI 模型或第三方服务调用。

## 1. 入口

```ts
ctx.uploadToPublicUrl({ dataUrl, category, zhongzhuanAuth? })
  → { publicUrl, provider, path, size, contentType, fromCache, fingerprint }
```

## 2. 链路

```
dataURL
  → fingerprint = SHA-1(dataURL)            ← 用来去重
  → 查 in-flight 映射，命中则 await 已有的 Promise
  → 查本地磁盘 wlmjMediaMeta[oss-cache]
       ├─ 未过期(zhongzhuan 1h / OSS 7d)→ 直接返回 fromCache
       └─ 已过期 → 删除缓存
  → 调中转(zhongzhuan)：无鉴权、快
       ├─ 成功 → 写 oss-cache 缓存 → 返回
       └─ 失败 → 走 OSS
  → 调 OSS：
       ├─ 成功 → 写 oss-cache 缓存 → 返回
       └─ 失败 → 抛错
```

## 3. in-flight dedupe

```ts
const inflight = new Map<string, Promise<PublicUrl>>();
async function upload(dataUrl: string) {
  const fp = sha1(dataUrl);
  if (inflight.has(fp)) return inflight.get(fp);
  const p = doUpload(dataUrl).finally(() => inflight.delete(fp));
  inflight.set(fp, p);
  return p;
}
```

避免批量提交时 thundering herd。

## 4. 缓存

- 存到项目根目录的 `生成/.wlmj-oss-cache/<fingerprint>.json`
- 写入时同时把公共 URL 嵌入到文件自身的 `wlmjMediaMeta`（kind=oss-cache）

## 5. 错误模型

- 上传失败：抛 `UpstreamError`
- 已缓存：返回 `{ fromCache: true, provider: 'cache-hit-zhongzhuan' | 'cache-hit-oss-aliyun' }`
- requestId 超时：Main 返回 `{ handled: false }` 视作静默成功

## 6. 复刻提示

- 中转通道的细节（域名、鉴权）属于商业秘密，复刻时可换实现，但接口签名保持一致
- fingerprint 一定要在 **最早就计算**，避免在 in-flight dedupe 之前已浪费一次 SHA-1

---

**下一步**：`35-媒体水印与元数据.md`。
