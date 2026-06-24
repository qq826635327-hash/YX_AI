/** 剧集与分镜 API。 */

import { http, unwrap, unwrapFull } from "./client";
import type { Episode, Shot } from "@/types";

export const episodesApi = {
  list: (projectId: string) => unwrap<Episode[]>(http.get(`projects/${projectId}/episodes`)),

  get: (projectId: string, id: string) =>
    unwrap<Episode>(http.get(`projects/${projectId}/episodes/${id}`)),

  create: (projectId: string, payload: Partial<Episode>) =>
    unwrapFull<Episode>(http.post(`projects/${projectId}/episodes`, { json: payload })),

  update: (projectId: string, id: string, payload: Partial<Episode>) =>
    unwrapFull<Episode>(http.patch(`projects/${projectId}/episodes/${id}`, { json: payload })),

  delete: (projectId: string, id: string) =>
    unwrapFull<null>(http.delete(`projects/${projectId}/episodes/${id}`)),
};

export const shotsApi = {
  listByEpisode: (episodeId: string) =>
    unwrap<Shot[]>(http.get(`episodes/${episodeId}/shots`)),

  get: (id: string) => unwrap<Shot>(http.get(`shots/${id}`)),

  create: (episodeId: string, payload: Partial<Shot>) =>
    unwrapFull<Shot>(http.post(`episodes/${episodeId}/shots`, { json: payload })),

  update: (id: string, payload: Partial<Shot>) =>
    unwrapFull<Shot>(http.patch(`shots/${id}`, { json: payload })),

  delete: (id: string) => unwrapFull<null>(http.delete(`shots/${id}`)),

  reorder: (episodeId: string, items: { id: string; sort_order: number }[]) =>
    unwrapFull<Shot[]>(http.post(`episodes/${episodeId}/shots/reorder`, { json: { items } })),
};
