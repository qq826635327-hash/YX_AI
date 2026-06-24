/** 页面容器通用包装：统一标题与内边距。 */

import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PageContainerProps {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  showBack?: boolean;
  backTo?: string;
}

export function PageContainer({ title, description, actions, children, className, showBack, backTo }: PageContainerProps) {
  const navigate = useNavigate();
  return (
    <div className="w-full p-6">
      {(showBack || title || description || actions) && (
        <div className="mb-6 flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            {showBack && (
              <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" onClick={() => backTo ? navigate(backTo) : navigate(-1)}>
                <ArrowLeft className="h-4 w-4" />
              </Button>
            )}
            <div>
              {title && <h1 className="text-xl font-bold tracking-tight">{title}</h1>}
              {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
            </div>
          </div>
          {actions && (
            <div className="flex flex-wrap items-center justify-end gap-2">
              {actions}
            </div>
          )}
        </div>
      )}
      <div className={cn(className)}>{children}</div>
    </div>
  );
}

/** 加载状态。 */
export function LoadingState() {
  return (
    <div className="flex h-40 items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted border-t-primary" />
    </div>
  );
}

/** 空状态。 */
export function EmptyState({ icon: Icon, title, description }: {
  icon?: React.ElementType;
  title: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/60 bg-card/50 py-16 text-center">
      {Icon && <Icon className="mb-3 h-10 w-10 text-primary/40" />}
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description && <p className="mt-1 text-xs text-muted-foreground">{description}</p>}
    </div>
  );
}
