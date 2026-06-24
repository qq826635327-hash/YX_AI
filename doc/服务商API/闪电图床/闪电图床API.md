---
created: 2026-06-23T13:09:39 (UTC +08:00)
tags: [闪电图床,免费图床,图片上传,图片外链,公共图床,公益图床,电商图床,图片托管,云存储,CDN加速,PicGo,WordPress,Typecho,API上传,批量上传,亚马逊图床,Shopify图床,图片转链接,免费图片存储,高速图床]
source: https://www.boltp.com/pages/api-docs
author: 
---

## 基本信息

-   请求方式：POST
-   请求类型：multipart/form-data
-   接口地址： [https://www.boltp.com/api/v2/upload](https://www.boltp.com/api/v2/upload)

___

## 请求头（Headers）

| 参数 | 类型 | 说明 |
|--------|--------|------------------|
| Accept | string | application/json |

___

## 请求参数（Form Data）

| 参数名 | 类型 | 必填 | 说明 |
|--------------|---------------|-----|---------------------------|
| file | file | 是 | 二进制图片文件 |
| storage_id | integer | 是 | 储存ID（免费用户：2 VIP用户：3） |
| album_id | integer | 否 | 相册ID（登录用户有效） |
| expired_at | string | 否 | 到期时间（yyyy-MM-dd HH:mm:ss） |
| tags[] | array[string] | 否 | 标签（登录用户有效） |
| is_public | boolean | 否 | 是否公开图片（默认 false） |
| is_remove_exif | boolean | 否 | 是否移除 EXIF 信息 |
| intro | string | 否 | 图片描述 |

___

## 请求示例

POST /api/v2/upload Content-Type: multipart/form-data

file = banner.png storage\_id = 1 album\_id = 0 expired\_at = 2026-01-01 00:00:00 tags\[\] = 街头摄影 tags\[\] = 城市建筑 is\_public = true is\_remove\_exif = true intro = 测试图片

___

## 成功响应（200）

status | string | 状态 message | string | 提示信息 time | integer | 时间戳

data 字段说明：

| 字段 | 类型 | 说明 |
|------------|---------|-------------|
| id | integer | 图片ID |
| name | string | 图片名称（不含扩展名） |
| filename | string | 文件名 |
| pathname | string | 物理路径 |
| mimetype | string | 文件类型 |
| extension | string | 扩展名 |
| md5 | string | MD5 值 |
| sha1 | string | SHA1 值 |
| width | integer | 宽度 |
| height | integer | 高度 |
| ip_address | string | 上传IP |
| public_url | string | 访问地址 |
| is_public | boolean | 是否公开 |
| intro | string | 描述 |

响应示例：

{ "status": "success", "message": "上传成功", "data": { "id": 1, "name": "banner", "filename": "banner.png", "pathname": "/storage/2026/01/banner.png", "mimetype": "image/png", "extension": "png", "md5": "xxxx", "sha1": "xxxx", "width": 1920, "height": 1080, "ip\_address": "127.0.0.1", "public\_url": "[https://img.xxx.com/banner.png](https://img.xxx.com/banner.png)", "is\_public": true, "intro": "测试图片" }, "time": 1700000000 }

___

## 错误响应

### 422 参数错误

{ "status": "error", "message": "参数错误", "data": { "errors": { "file": \["文件不能为空"\], "expired\_at": \["时间格式错误"\], "tags": \["格式错误"\], "is\_public": \["类型错误"\] } }, "time": 1700000000 }

___

### 429 超出频率限制

{ "status": "error", "message": "请求过于频繁", "data": null, "time": 1700000000 }

___
