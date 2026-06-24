/** React Query Hooks：业务实体（角色/场景/道具/剧集/分镜）。 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { charactersApi, scenesApi, propsApi } from "@/api/business";
import { episodesApi, shotsApi } from "@/api/episodes";
import { shotReferencesApi } from "@/api/shotReferences";
import { assetsApi } from "@/api/assets";
import { toast } from "@/stores/ui";

// ============================================================
// 角色
// ============================================================

export const charKeys = {
  all: ["characters"] as const,
  list: (projectId: string) => [...charKeys.all, "list", projectId] as const,
  detail: (projectId: string, id: string) => [...charKeys.all, "detail", projectId, id] as const,
};

export function useCharacters(projectId: string, charType?: string) {
  return useQuery({
    queryKey: [...charKeys.list(projectId), charType],
    queryFn: () => charactersApi.list(projectId, charType),
    enabled: !!projectId,
  });
}

export function useCreateCharacter(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Parameters<typeof charactersApi.create>[1]) =>
      charactersApi.create(projectId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: charKeys.list(projectId) });
      toast.success("角色已创建");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useUpdateCharacter(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      charactersApi.update(projectId, id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: charKeys.list(projectId) });
      toast.success("角色已更新");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useDeleteCharacter(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => charactersApi.delete(projectId, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: charKeys.list(projectId) });
      toast.success("角色已删除");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useCharacter(projectId: string, id: string) {
  return useQuery({
    queryKey: charKeys.detail(projectId, id),
    queryFn: () => charactersApi.get(projectId, id),
    enabled: !!projectId && !!id,
  });
}

// ============================================================
// 场景
// ============================================================

export const sceneKeys = {
  all: ["scenes"] as const,
  list: (projectId: string) => [...sceneKeys.all, "list", projectId] as const,
  detail: (projectId: string, id: string) => [...sceneKeys.all, "detail", projectId, id] as const,
};

export function useScenes(projectId: string) {
  return useQuery({
    queryKey: sceneKeys.list(projectId),
    queryFn: () => scenesApi.list(projectId),
    enabled: !!projectId,
  });
}

export function useCreateScene(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Parameters<typeof scenesApi.create>[1]) => scenesApi.create(projectId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: sceneKeys.list(projectId) });
      toast.success("场景已创建");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useUpdateScene(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      scenesApi.update(projectId, id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: sceneKeys.list(projectId) });
      toast.success("场景已更新");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useDeleteScene(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => scenesApi.delete(projectId, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: sceneKeys.list(projectId) });
      toast.success("场景已删除");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useScene(projectId: string, id: string) {
  return useQuery({
    queryKey: sceneKeys.detail(projectId, id),
    queryFn: () => scenesApi.get(projectId, id),
    enabled: !!projectId && !!id,
  });
}

// ============================================================
// 道具
// ============================================================

export const propKeys = {
  all: ["props"] as const,
  list: (projectId: string) => [...propKeys.all, "list", projectId] as const,
  detail: (projectId: string, id: string) => [...propKeys.all, "detail", projectId, id] as const,
};

export function useProps(projectId: string) {
  return useQuery({
    queryKey: propKeys.list(projectId),
    queryFn: () => propsApi.list(projectId),
    enabled: !!projectId,
  });
}

export function useCreateProp(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Parameters<typeof propsApi.create>[1]) => propsApi.create(projectId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: propKeys.list(projectId) });
      toast.success("道具已创建");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useUpdateProp(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      propsApi.update(projectId, id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: propKeys.list(projectId) });
      toast.success("道具已更新");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useDeleteProp(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => propsApi.delete(projectId, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: propKeys.list(projectId) });
      toast.success("道具已删除");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useProp(projectId: string, id: string) {
  return useQuery({
    queryKey: propKeys.detail(projectId, id),
    queryFn: () => propsApi.get(projectId, id),
    enabled: !!projectId && !!id,
  });
}

// ============================================================
// 剧集与分镜
// ============================================================

export const episodeKeys = {
  all: ["episodes"] as const,
  list: (projectId: string) => [...episodeKeys.all, "list", projectId] as const,
  shots: (episodeId: string) => ["shots", episodeId] as const,
};

export function useEpisodes(projectId: string) {
  return useQuery({
    queryKey: episodeKeys.list(projectId),
    queryFn: () => episodesApi.list(projectId),
    enabled: !!projectId,
  });
}

export function useShots(episodeId: string) {
  return useQuery({
    queryKey: episodeKeys.shots(episodeId),
    queryFn: () => shotsApi.listByEpisode(episodeId),
    enabled: !!episodeId,
  });
}

export function useUpdateShot(_projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      shotsApi.update(id, payload),
    onSuccess: (_data, { id }) => {
      // invalidate 列表 + 单条详情，确保右侧属性面板也刷新
      qc.invalidateQueries({ queryKey: ["shots"] });
      qc.invalidateQueries({ queryKey: ["shot", id] });
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

// ============================================================
// 剧集增删
// ============================================================

export function useCreateEpisode(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<import("@/types").Episode>) =>
      episodesApi.create(projectId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: episodeKeys.list(projectId) });
      toast.success("剧集已创建");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useDeleteEpisode(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => episodesApi.delete(projectId, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: episodeKeys.list(projectId) });
      toast.success("剧集已删除");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useUpdateEpisode(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: string } & Partial<import("@/types").Episode>) =>
      episodesApi.update(projectId, id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: episodeKeys.list(projectId) });
      toast.success("剧集已更新");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

// ============================================================
// 分镜增删
// ============================================================

export function useCreateShot(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ episodeId, payload }: { episodeId: string; payload: Partial<import("@/types").Shot> }) =>
      shotsApi.create(episodeId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shots"] });
      qc.invalidateQueries({ queryKey: episodeKeys.list(projectId) });
      toast.success("分镜已创建");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useDeleteShot(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => shotsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shots"] });
      qc.invalidateQueries({ queryKey: episodeKeys.list(projectId) });
      toast.success("分镜已删除");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

// ============================================================
// 分镜关联引用
// ============================================================

export function useShotReferences(shotId: string) {
  return useQuery({
    queryKey: ["shot-references", shotId],
    queryFn: () => shotReferencesApi.get(shotId),
    enabled: !!shotId,
  });
}

export function useAddShotCharacters(shotId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entityIds: string[]) => shotReferencesApi.addCharacters(shotId, entityIds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shot-references", shotId] });
      toast.success("已添加关联角色");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useRemoveShotCharacter(shotId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (characterId: string) => shotReferencesApi.removeCharacter(shotId, characterId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shot-references", shotId] });
      toast.success("已移除关联角色");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useAddShotScenes(shotId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entityIds: string[]) => shotReferencesApi.addScenes(shotId, entityIds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shot-references", shotId] });
      toast.success("已添加关联场景");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useRemoveShotScene(shotId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sceneId: string) => shotReferencesApi.removeScene(shotId, sceneId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shot-references", shotId] });
      toast.success("已移除关联场景");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useAddShotProps(shotId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entityIds: string[]) => shotReferencesApi.addProps(shotId, entityIds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shot-references", shotId] });
      toast.success("已添加关联道具");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useRemoveShotProp(shotId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (propId: string) => shotReferencesApi.removeProp(shotId, propId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shot-references", shotId] });
      toast.success("已移除关联道具");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

// ============================================================
// 素材（按 target_type + target_id 拉取）
// ============================================================

export const assetKeys = {
  all: ["assets"] as const,
  byTarget: (projectId: string, targetType: string, targetId: string) =>
    [...assetKeys.all, "target", projectId, targetType, targetId] as const,
};

export function useAssets(projectId: string, targetType?: string, targetId?: string) {
  return useQuery({
    queryKey: assetKeys.byTarget(projectId, targetType || "", targetId || ""),
    queryFn: () =>
      assetsApi.list(projectId, {
        target_type: targetType,
        target_id: targetId,
      }),
    enabled: !!projectId && !!targetType && !!targetId,
  });
}

