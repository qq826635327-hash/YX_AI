import { render, screen } from "@testing-library/react";
import { Badge } from "./badge";

describe("Badge", () => {
  it("renders children text", () => {
    render(<Badge>测试标签</Badge>);
    expect(screen.getByText("测试标签")).toBeInTheDocument();
  });

  it("renders as a div element", () => {
    const { container } = render(<Badge>content</Badge>);
    const badge = container.firstChild as HTMLElement;
    expect(badge).toBeInTheDocument();
    expect(badge.tagName).toBe("DIV");
  });

  it("applies default variant classes", () => {
    const { container } = render(<Badge>default</Badge>);
    const badge = container.firstChild as HTMLElement;
    // default variant should include bg-primary
    expect(badge.className).toContain("bg-primary");
  });

  it("applies secondary variant classes", () => {
    const { container } = render(<Badge variant="secondary">sec</Badge>);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("bg-secondary");
  });

  it("applies destructive variant classes", () => {
    const { container } = render(<Badge variant="destructive">del</Badge>);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("bg-destructive");
  });

  it("applies outline variant classes", () => {
    const { container } = render(<Badge variant="outline">out</Badge>);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("text-foreground");
  });

  it("applies success variant classes", () => {
    const { container } = render(<Badge variant="success">ok</Badge>);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("green");
  });

  it("applies warning variant classes", () => {
    const { container } = render(<Badge variant="warning">warn</Badge>);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("amber");
  });

  it("merges custom className", () => {
    const { container } = render(<Badge className="my-custom-class">test</Badge>);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("my-custom-class");
  });

  it("passes additional HTML attributes", () => {
    const { container } = render(<Badge data-testid="my-badge">test</Badge>);
    const badge = container.firstChild as HTMLElement;
    expect(badge.getAttribute("data-testid")).toBe("my-badge");
  });
});
