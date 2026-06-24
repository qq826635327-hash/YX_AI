/** 素材 API。 */

import { http, unwrap, unwrapFull } from "./client";
import type { Asset } from "@/types";

export const assetsApi = {
  list: (projectId: string, params?: { category?: string; asset_type?: string; target_type?: string; target_id?: string }) =>
    unwrap<Asset[]>(http.get("assets", { searchParams: { project_id: projectId, ...params } })),

  get: (id: string) => unwrap<Asset>(http.get(`assets/${id}`)),

  fileUrl: (id: string) => `/api/assets/${id}/file`,

  upload: (assetId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return unwrapFull<Asset>(http.post(`assets/${assetId}/upload`, { body: formData }));
  },

  uploadNew: (params: {projectId: string, category: string, file: File, target_type?: string, target_id?: string}) => {
    const formData = new FormData();
    formData.append("file", params.file);
    const searchParams: Record<string, string> = { category: params.category };
    if (params.target_type) searchParams.target_type = params.target_type;
    if (params.target_id) searchParams.target_id = params.target_id;
    return unwrapFull<Asset>(
      http.post(`assets/projects/${params.projectId}/upload`, {
        body: formData,
        searchParams,
      })
    );
  },

  delete: (id: string, deleteFile = false) =>
    unwrapFull<null>(http.delete(`assets/${id}`, { searchParams: { delete_file: deleteFile } })),

  /** 双向同步：清理丢失文件的 DB 记录 + 发现磁盘上未注册的文件 */
  sync: (projectId: string) =>
    unwrap<{ checked: number; cleaned: number; discovered: number; errors: number; details: { action?: string; asset_id: string; file_name: string; file_path?: string; target_type?: string; target_id?: string }[] }>(
      http.post("assets/sync", { searchParams: { project_id: projectId }, json: {} })
    ),

  /** 双向同步目录：DB↔磁盘（补建缺失目录 + 清理孤立 DB 记录） */
  syncDirs: (projectId: string, direction: "both" | "db_to_disk" | "disk_to_db" = "both") =>
    unwrapFull<{ db_to_disk?: { created: number; skipped: number; removed: number; errors: number }; disk_to_db?: { checked: number; deleted: number; errors: number }; created?: number; skipped?: number; removed?: number; checked?: number; deleted?: number; errors?: number }>(
      http.post("assets/sync-dirs", { searchParams: { project_id: projectId, direction } })
    ),

  /** 用系统文件管理器打开本地目录 */
  openDir: (path: string) =>
    unwrapFull<null>(http.post("assets/open-dir", { searchParams: { path } })),
};
