/** 剧本 API。 */

import { http, unwrap, unwrapFull } from "./client";
import type { ScriptDocument } from "@/types";

export const scriptApi = {
  get: (projectId: string) => unwrap<ScriptDocument | { raw_text: string }>(http.get(`projects/${projectId}/script`)),

  update: (projectId: string, rawText: string) =>
    unwrapFull<ScriptDocument>(http.put(`projects/${projectId}/script`, { json: { raw_text: rawText } })),

  parse: (projectId: string, force = false) =>
    unwrapFull<{ script_id: string; status: string }>(
      http.post(`projects/${projectId}/script/parse`, { json: { force } })
    ),
};
