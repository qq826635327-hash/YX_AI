/** 画风预置 API。 */

import { http, unwrap, unwrapFull } from "./client";
import type { StylePreset } from "@/types";

export interface StylePresetCreate {
  title: string;
  description: string;
  is_default?: boolean;
  sort_order?: number;
}

export interface StylePresetUpdate {
  title?: string;
  description?: string;
  is_default?: boolean;
  sort_order?: number;
}

export const stylePresetsApi = {
  list: () => unwrap<StylePreset[]>(http.get("style-presets")),

  get: (id: string) => unwrap<StylePreset>(http.get(`style-presets/${id}`)),

  create: (payload: StylePresetCreate) =>
    unwrapFull<StylePreset>(http.post("style-presets", { json: payload })),

  update: (id: string, payload: StylePresetUpdate) =>
    unwrapFull<StylePreset>(http.put(`style-presets/${id}`, { json: payload })),

  reorder: (orderedIds: string[]) =>
    unwrapFull<StylePreset[]>(http.put("style-presets/reorder", { json: { ordered_ids: orderedIds } })),

  delete: (id: string) => unwrapFull<null>(http.delete(`style-presets/${id}`)),
};
