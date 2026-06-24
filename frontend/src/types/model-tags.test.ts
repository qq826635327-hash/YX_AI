import { MODEL_TAG_LABELS, PROMPT_TEMPLATE_TYPE_LABELS } from "./index";
import type { ModelTag, PromptTemplateType } from "./index";

describe("MODEL_TAG_LABELS", () => {
  it("is a non-empty record", () => {
    expect(typeof MODEL_TAG_LABELS).toBe("object");
    expect(Object.keys(MODEL_TAG_LABELS).length).toBeGreaterThan(0);
  });

  it("has string values", () => {
    for (const [, value] of Object.entries(MODEL_TAG_LABELS)) {
      expect(typeof value).toBe("string");
      expect(value.length).toBeGreaterThan(0);
    }
  });

  it("contains all expected model tags", () => {
    const expectedTags: ModelTag[] = [
      "text_reasoning",
      "image_generation",
      "image_to_image",
      "video_generation",
    ];
    for (const tag of expectedTags) {
      expect(MODEL_TAG_LABELS[tag]).toBeDefined();
      expect(typeof MODEL_TAG_LABELS[tag]).toBe("string");
    }
  });

  it("maps text_reasoning to 文本推理", () => {
    expect(MODEL_TAG_LABELS["text_reasoning"]).toBe("文本推理");
  });

  it("maps image_generation to 图片生成", () => {
    expect(MODEL_TAG_LABELS["image_generation"]).toBe("图片生成");
  });

  it("maps video_generation to 视频生成", () => {
    expect(MODEL_TAG_LABELS["video_generation"]).toBe("视频生成");
  });
});

describe("PROMPT_TEMPLATE_TYPE_LABELS", () => {
  it("is a non-empty record", () => {
    expect(typeof PROMPT_TEMPLATE_TYPE_LABELS).toBe("object");
    expect(Object.keys(PROMPT_TEMPLATE_TYPE_LABELS).length).toBeGreaterThan(0);
  });

  it("has string values", () => {
    for (const [, value] of Object.entries(PROMPT_TEMPLATE_TYPE_LABELS)) {
      expect(typeof value).toBe("string");
      expect(value.length).toBeGreaterThan(0);
    }
  });

  it("contains all expected template types", () => {
    const expectedTypes: PromptTemplateType[] = [
      "character",
      "scene",
      "prop",
      "episode",
      "shot",
    ];
    for (const t of expectedTypes) {
      expect(PROMPT_TEMPLATE_TYPE_LABELS[t]).toBeDefined();
    }
  });

  it("maps character to 角色提取", () => {
    expect(PROMPT_TEMPLATE_TYPE_LABELS["character"]).toBe("角色提取");
  });

  it("maps shot to 分镜拆分", () => {
    expect(PROMPT_TEMPLATE_TYPE_LABELS["shot"]).toBe("分镜拆分");
  });
});
