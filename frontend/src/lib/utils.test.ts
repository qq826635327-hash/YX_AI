import { cn, formatTime, formatSize, taskStatusMap, charTypeMap } from "./utils";

describe("cn utility", () => {
  it("merges class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "end")).toBe("base end");
  });

  it("handles undefined and null", () => {
    expect(cn("a", undefined, null, "b")).toBe("a b");
  });

  it("deduplicates tailwind classes via twMerge", () => {
    // twMerge should resolve conflicting Tailwind classes
    const result = cn("px-2 py-1", "px-4");
    expect(result).toContain("py-1");
    expect(result).toContain("px-4");
    expect(result).not.toContain("px-2");
  });
});

describe("formatTime", () => {
  it("returns '-' for undefined", () => {
    expect(formatTime(undefined)).toBe("-");
  });

  it("returns '-' for empty string", () => {
    expect(formatTime("")).toBe("-");
  });

  it("returns '-' for invalid date string", () => {
    expect(formatTime("not-a-date")).toBe("-");
  });

  it("formats a valid ISO date string", () => {
    const result = formatTime("2026-06-21T10:30:00Z");
    // Should contain year and month at minimum
    expect(result).toContain("2026");
    expect(result).not.toBe("-");
  });

  it("formats a Date object", () => {
    const d = new Date(2026, 5, 21, 10, 30); // month is 0-indexed
    const result = formatTime(d);
    expect(result).toContain("2026");
    expect(result).not.toBe("-");
  });
});

describe("formatSize", () => {
  it("returns '-' for undefined", () => {
    expect(formatSize(undefined)).toBe("-");
  });

  it("returns '-' for null", () => {
    expect(formatSize(null)).toBe("-");
  });

  it("returns '-' for 0", () => {
    expect(formatSize(0)).toBe("-");
  });

  it("formats bytes", () => {
    expect(formatSize(500)).toBe("500.0 B");
  });

  it("formats kilobytes", () => {
    expect(formatSize(1024)).toBe("1.0 KB");
  });

  it("formats megabytes", () => {
    expect(formatSize(1024 * 1024)).toBe("1.0 MB");
  });

  it("formats gigabytes", () => {
    expect(formatSize(1024 * 1024 * 1024)).toBe("1.0 GB");
  });

  it("formats fractional KB", () => {
    expect(formatSize(1536)).toBe("1.5 KB");
  });
});

describe("taskStatusMap", () => {
  it("has entries for all expected statuses", () => {
    const expectedKeys = ["pending", "queued", "running", "succeeded", "failed", "cancelled"];
    for (const key of expectedKeys) {
      expect(taskStatusMap[key]).toBeDefined();
      expect(typeof taskStatusMap[key].label).toBe("string");
      expect(typeof taskStatusMap[key].color).toBe("string");
    }
  });

  it("maps succeeded to 成功", () => {
    expect(taskStatusMap["succeeded"].label).toBe("成功");
  });

  it("maps failed to 失败", () => {
    expect(taskStatusMap["failed"].label).toBe("失败");
  });
});

describe("charTypeMap", () => {
  it("maps protagonist to 主角", () => {
    expect(charTypeMap["protagonist"]).toBe("主角");
  });

  it("maps supporting to 配角", () => {
    expect(charTypeMap["supporting"]).toBe("配角");
  });

  it("maps extra to 群演", () => {
    expect(charTypeMap["extra"]).toBe("群演");
  });
});
