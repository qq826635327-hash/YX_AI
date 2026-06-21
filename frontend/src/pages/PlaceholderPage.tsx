/** 占位页面组件。 */
export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
      <h2 className="text-2xl font-bold mb-2">{title}</h2>
      <p className="text-sm">页面开发中，敬请期待…</p>
    </div>
  );
}
