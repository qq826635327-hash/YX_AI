/** 分镜关联引用 API。 */

import { http, unwrap, unwrapFull } from "./client";
import type { ShotReferences } from "@/types";

export const shotReferencesApi = {
  get: (shotId: string) =>
    unwrap<ShotReferences>(http.get(`shots/${shotId}/references`)),

  addCharacters: (shotId: string, entityIds: string[]) =>
    unwrapFull<{ added: number }>(http.post(`shots/${shotId}/characters`, { json: { entity_ids: entityIds } })),

  removeCharacter: (shotId: string, characterId: string) =>
    unwrapFull<null>(http.delete(`shots/${shotId}/characters/${characterId}`)),

  addScenes: (shotId: string, entityIds: string[]) =>
    unwrapFull<{ added: number }>(http.post(`shots/${shotId}/scenes`, { json: { entity_ids: entityIds } })),

  removeScene: (shotId: string, sceneId: string) =>
    unwrapFull<null>(http.delete(`shots/${shotId}/scenes/${sceneId}`)),

  addProps: (shotId: string, entityIds: string[]) =>
    unwrapFull<{ added: number }>(http.post(`shots/${shotId}/props`, { json: { entity_ids: entityIds } })),

  removeProp: (shotId: string, propId: string) =>
    unwrapFull<null>(http.delete(`shots/${shotId}/props/${propId}`)),
};
