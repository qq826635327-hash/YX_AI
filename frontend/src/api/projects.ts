/** 项目 API。 */

import { http, unwrap, unwrapFull, unwrapPaginated } from "./client";
import type { Project, ProjectCreate, ProjectUpdate } from "@/types";

export const projectsApi = {
  list: (params?: { status?: string; keyword?: string; page?: number; page_size?: number }) =>
    unwrapPaginated<Project>(http.get("projects", { searchParams: params })),

  get: (id: string) => unwrap<Project>(http.get(`projects/${id}`)),

  create: (payload: ProjectCreate) =>
    unwrapFull<Project>(http.post("projects", { json: payload })),

  update: (id: string, payload: ProjectUpdate) =>
    unwrapFull<Project>(http.patch(`projects/${id}`, { json: payload })),

  delete: (id: string, deleteFiles = false) =>
    unwrapFull<null>(http.delete(`projects/${id}`, { searchParams: { delete_files: deleteFiles } })),
};
