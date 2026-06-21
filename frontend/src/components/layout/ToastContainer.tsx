/** Toast 通知容器。 */

import { useUiStore } from "@/stores/ui";
import { cn } from "@/lib/utils";
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from "lucide-react";

const variantConfig = {
  default: { icon: Info, className: "border-border bg-card" },
  success: { icon: CheckCircle2, className: "border-green-500/30 bg-green-500/10" },
  error: { icon: XCircle, className: "border-red-500/30 bg-red-500/10" },
  warning: { icon: AlertTriangle, className: "border-amber-500/30 bg-amber-500/10" },
};

export function ToastContainer() {
  const { toasts, removeToast } = useUiStore();

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
      {toasts.map((t) => {
        const config = variantConfig[t.variant];
        const Icon = config.icon;
        return (
          <div
            key={t.id}
            className={cn(
              "flex w-80 items-start gap-3 rounded-lg border p-4 shadow-lg animate-fade-in",
              config.className
            )}
          >
            <Icon className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="flex-1 min-w-0">
              {t.title && <p className="text-sm font-semibold">{t.title}</p>}
              {t.description && (
                <p className="text-sm text-muted-foreground break-words">{t.description}</p>
              )}
            </div>
            <button
              onClick={() => removeToast(t.id)}
              className="shrink-0 rounded p-0.5 hover:bg-black/10 dark:hover:bg-white/10"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
