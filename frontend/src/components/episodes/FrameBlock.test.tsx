import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import FrameBlock from "./FrameBlock";
import { RefreshCw } from "lucide-react";

// Provide a minimal icon component for testing
const MockIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg data-testid="mock-icon" {...props} />
);

describe("FrameBlock", () => {
  const defaultProps = {
    title: "首帧",
    icon: RefreshCw,
    prompt: "a beautiful sunset",
    assetId: undefined,
    status: "none" as const,
    isVideo: false,
    onPromptChange: vi.fn(),
    onGenerate: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders title text", () => {
    render(<FrameBlock {...defaultProps} />);
    expect(screen.getByText("首帧")).toBeInTheDocument();
  });

  it("renders textarea with prompt value", () => {
    render(<FrameBlock {...defaultProps} />);
    const textarea = screen.getByPlaceholderText("首帧提示词...");
    expect(textarea).toBeInTheDocument();
    expect((textarea as HTMLTextAreaElement).value).toBe("a beautiful sunset");
  });

  it("shows generate button when no asset", () => {
    render(<FrameBlock {...defaultProps} />);
    expect(screen.getByText("生成图片")).toBeInTheDocument();
  });

  it("shows 生成视频 button when isVideo is true and no asset", () => {
    render(<FrameBlock {...defaultProps} isVideo={true} />);
    expect(screen.getByText("生成视频")).toBeInTheDocument();
  });

  it("calls onGenerate when generate button is clicked", async () => {
    const user = userEvent.setup();
    render(<FrameBlock {...defaultProps} />);
    const button = screen.getByText("生成图片");
    await user.click(button);
    expect(defaultProps.onGenerate).toHaveBeenCalledOnce();
  });

  it("does not show badge when status is none", () => {
    render(<FrameBlock {...defaultProps} />);
    expect(screen.queryByText("未生成")).not.toBeInTheDocument();
  });

  it("shows badge when status is not none", () => {
    render(<FrameBlock {...defaultProps} status="generating" />);
    expect(screen.getByText("生成中")).toBeInTheDocument();
  });

  it("shows ready badge for ready status", () => {
    render(<FrameBlock {...defaultProps} status="ready" />);
    expect(screen.getByText("已就绪")).toBeInTheDocument();
  });

  it("shows failed badge for failed status", () => {
    render(<FrameBlock {...defaultProps} status="failed" />);
    expect(screen.getByText("失败")).toBeInTheDocument();
  });

  it("renders img element when assetId is provided and not video", () => {
    const { container } = render(
      <FrameBlock {...defaultProps} assetId="abc123" status="ready" />
    );
    const img = container.querySelector("img");
    expect(img).toBeInTheDocument();
    expect(img?.getAttribute("src")).toBe("/api/assets/abc123/file");
  });

  it("renders video element when assetId is provided and isVideo", () => {
    const { container } = render(
      <FrameBlock {...defaultProps} assetId="vid456" status="ready" isVideo={true} />
    );
    const video = container.querySelector("video");
    expect(video).toBeInTheDocument();
    expect(video?.getAttribute("src")).toBe("/api/assets/vid456/file");
  });
});
