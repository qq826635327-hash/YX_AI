/** 提示词模板 API。 */

import { http, unwrap, unwrapFull } from "./client";
import type { PromptTemplate, PromptTemplateCreate, PromptTemplateType, PromptTemplateUpdate } from "@/types";

export const promptTemplatesApi = {
  list: (template_type?: PromptTemplateType) =>
    unwrap<PromptTemplate[]>(
      http.get("prompt-templates", {
        searchParams: template_type ? { template_type } : undefined,
      })
    ),

  get: (id: string) => unwrap<PromptTemplate>(http.get(`prompt-templates/${id}`)),

  create: (payload: PromptTemplateCreate) =>
    unwrapFull<PromptTemplate>(http.post("prompt-templates", { json: payload })),

  update: (id: string, payload: PromptTemplateUpdate) =>
    unwrapFull<PromptTemplate>(http.put(`prompt-templates/${id}`, { json: payload })),

  delete: (id: string) => unwrapFull<null>(http.delete(`prompt-templates/${id}`)),
};
