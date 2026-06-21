/** 角色 / 场景 / 道具 API。 */

import { http, unwrap, unwrapFull } from "./client";
import type { Character, Scene, Prop } from "@/types";

// ============================================================
// 角色
// ============================================================

export const charactersApi = {
  list: (projectId: string, charType?: string) =>
    unwrap<Character[]>(http.get(`projects/${projectId}/characters`, {
      searchParams: charType ? { char_type: charType } : undefined,
    })),

  get: (projectId: string, id: string) =>
    unwrap<Character>(http.get(`projects/${projectId}/characters/${id}`)),

  create: (projectId: string, payload: Partial<Character>) =>
    unwrapFull<Character>(http.post(`projects/${projectId}/characters`, { json: payload })),

  update: (projectId: string, id: string, payload: Partial<Character>) =>
    unwrapFull<Character>(http.patch(`projects/${projectId}/characters/${id}`, { json: payload })),

  delete: (projectId: string, id: string) =>
    unwrapFull<null>(http.delete(`projects/${projectId}/characters/${id}`)),
};

// ============================================================
// 场景
// ============================================================

export const scenesApi = {
  list: (projectId: string) => unwrap<Scene[]>(http.get(`projects/${projectId}/scenes`)),

  get: (projectId: string, id: string) =>
    unwrap<Scene>(http.get(`projects/${projectId}/scenes/${id}`)),

  create: (projectId: string, payload: Partial<Scene>) =>
    unwrapFull<Scene>(http.post(`projects/${projectId}/scenes`, { json: payload })),

  update: (projectId: string, id: string, payload: Partial<Scene>) =>
    unwrapFull<Scene>(http.patch(`projects/${projectId}/scenes/${id}`, { json: payload })),

  delete: (projectId: string, id: string) =>
    unwrapFull<null>(http.delete(`projects/${projectId}/scenes/${id}`)),
};

// ============================================================
// 道具
// ============================================================

export const propsApi = {
  list: (projectId: string) => unwrap<Prop[]>(http.get(`projects/${projectId}/props`)),

  get: (projectId: string, id: string) =>
    unwrap<Prop>(http.get(`projects/${projectId}/props/${id}`)),

  create: (projectId: string, payload: Partial<Prop>) =>
    unwrapFull<Prop>(http.post(`projects/${projectId}/props`, { json: payload })),

  update: (projectId: string, id: string, payload: Partial<Prop>) =>
    unwrapFull<Prop>(http.patch(`projects/${projectId}/props/${id}`, { json: payload })),

  delete: (projectId: string, id: string) =>
    unwrapFull<null>(http.delete(`projects/${projectId}/props/${id}`)),
};
