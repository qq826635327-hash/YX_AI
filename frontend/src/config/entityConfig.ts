import type { LucideIcon } from "lucide-react";
import type { Character, Scene, Prop } from "@/types";

/** 编辑框字段配置 */
export interface EditFieldConfig {
  name: string;
  label: string;
  type: "text" | "textarea" | "tabs";
  placeholder?: string;
  required?: boolean;
  rows?: number;
  /** type=tabs 时使用 */
  options?: { value: string; label: string }[];
}

/** 实体类型配置（驱动通用页面） */
export interface EntityConfig<T> {
  /** 实体类型标识 */
  entityType: "character" | "scene" | "prop";
  /** 页面标题 */
  title: string;
  /** 页面描述 */
  description: string;
  /** 空状态图标 */
  emptyIcon: LucideIcon;
  /** 生成目标类型 */
  targetType: "character" | "scene" | "prop";
  /** 详情页路由 */
  detailPath: (projectId: string, entity: T) => string;
  /** Tabs 筛选配置（可选，仅角色） */
  tabs?: { value: string; label: string }[];
  /** Tabs 筛选函数（可选） */
  tabFilter?: (entity: T, activeTab: string) => boolean;
  /** 角标函数（可选，仅角色） */
  getBadge?: (entity: T) => string | undefined;
  /** 编辑框字段配置 */
  editFields: EditFieldConfig[];
  /** 从实体提取初始表单值 */
  getInitialValues: (entity: T | null) => Record<string, any>;
  /** 从表单值构建提交数据 */
  buildSubmitData: (formData: Record<string, any>) => Partial<T>;
  /** 编辑对话框标题 */
  getDialogTitle: (entity: T | null) => string;
  /** 编辑对话框描述 */
  getDialogDescription: (entity: T | null) => string;
}

import {
  Users,
  Map,
  Package,
} from "lucide-react";
import { charTypeMap } from "@/lib/utils";

// ——— Character Config ———
export const characterConfig: EntityConfig<Character> = {
  entityType: "character",
  title: "角色",
  description: "管理项目角色设定与角色图生成",
  emptyIcon: Users,
  targetType: "character",
  detailPath: (projectId, char) =>
    `/projects/${projectId}/characters/${char.id}`,
  tabs: [
    { value: "all", label: "全部" },
    { value: "protagonist", label: "主角" },
    { value: "supporting", label: "配角" },
    { value: "extra", label: "群演" },
  ],
  tabFilter: (char, activeTab) =>
    activeTab === "all" || char.char_type === activeTab,
  getBadge: (char) => charTypeMap[char.char_type],
  editFields: [
    { name: "name", label: "名称 *", type: "text", placeholder: "角色名称", required: true },
    {
      name: "char_type",
      label: "分类",
      type: "tabs",
      options: [
        { value: "protagonist", label: "主角" },
        { value: "supporting", label: "配角" },
        { value: "extra", label: "群演" },
      ],
    },
    { name: "description", label: "描述", type: "textarea", placeholder: "角色背景、性格等", rows: 3 },
    { name: "settings", label: "设定（用于生成）", type: "textarea", placeholder: "外貌、服装等生成提示词", rows: 3 },
  ],
  getInitialValues: (char) => ({
    name: char?.name || "",
    char_type: char?.char_type || "supporting",
    description: char?.description || "",
    settings: char?.settings || "",
  }),
  buildSubmitData: (formData) => ({
    name: formData.name?.trim(),
    char_type: formData.char_type,
    description: formData.description,
    settings: formData.settings,
  }),
  getDialogTitle: (char) => (char ? "编辑角色" : "新建角色"),
  getDialogDescription: (char) => (char ? "修改角色信息" : "创建一个新角色"),
};

// ——— Scene Config ———
export const sceneConfig: EntityConfig<Scene> = {
  entityType: "scene",
  title: "场景",
  description: "管理项目场景设定与场景图生成",
  emptyIcon: Map,
  targetType: "scene",
  detailPath: (projectId, scene) =>
    `/projects/${projectId}/scenes/${scene.id}`,
  editFields: [
    { name: "name", label: "名称 *", type: "text", placeholder: "场景名称", required: true },
    { name: "description", label: "描述", type: "textarea", placeholder: "场景描述", rows: 3 },
    { name: "settings", label: "设定（用于生成）", type: "textarea", placeholder: "环境、氛围等生成提示词", rows: 3 },
  ],
  getInitialValues: (scene) => ({
    name: scene?.name || "",
    description: scene?.description || "",
    settings: scene?.settings || "",
  }),
  buildSubmitData: (formData) => ({
    name: formData.name?.trim(),
    description: formData.description,
    settings: formData.settings,
  }),
  getDialogTitle: (scene) => (scene ? "编辑场景" : "新建场景"),
  getDialogDescription: (scene) => (scene ? "修改场景信息" : "创建一个新场景"),
};

// ——— Prop Config ———
export const propConfig: EntityConfig<Prop> = {
  entityType: "prop",
  title: "道具",
  description: "管理项目道具设定与道具图生成",
  emptyIcon: Package,
  targetType: "prop",
  detailPath: (projectId, prop) =>
    `/projects/${projectId}/props/${prop.id}`,
  editFields: [
    { name: "name", label: "名称 *", type: "text", placeholder: "道具名称", required: true },
    { name: "description", label: "描述", type: "textarea", placeholder: "道具描述", rows: 3 },
    { name: "settings", label: "设定（用于生成）", type: "textarea", placeholder: "外观、材质等生成提示词", rows: 3 },
  ],
  getInitialValues: (prop) => ({
    name: prop?.name || "",
    description: prop?.description || "",
    settings: prop?.settings || "",
  }),
  buildSubmitData: (formData) => ({
    name: formData.name?.trim(),
    description: formData.description,
    settings: formData.settings,
  }),
  getDialogTitle: (prop) => (prop ? "编辑道具" : "新建道具"),
  getDialogDescription: (prop) => (prop ? "修改道具信息" : "创建一个新道具"),
};
