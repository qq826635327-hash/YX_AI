/**
 * 异步确认对话框：替代原生 confirm()，避免同步阻塞主线程导致 rAF 心跳误报。
 *
 * 用法：
 *   const confirm = useConfirm();
 *   const ok = await confirm({ title: "确认删除", description: "删除后不可恢复" });
 *   if (!ok) return;
 *
 * 原理：调用 confirm() 时返回 Promise，用户点确认 resolve(true)，取消/关闭 resolve(false)。
 * 对话框期间主线程正常运行，rAF 不受影响。
 */

import { useCallback, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface ConfirmOptions {
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  variant?: "default" | "destructive";
}

interface ConfirmState extends ConfirmOptions {
  open: boolean;
  resolver: ((value: boolean) => void) | null;
}

const defaultState: ConfirmState = {
  open: false,
  title: "",
  description: "",
  confirmText: "确认",
  cancelText: "取消",
  variant: "default",
  resolver: null,
};

/** 全局挂载一次的确认对话框组件 */
export function ConfirmDialog() {
  const [state, setState] = useState<ConfirmState>(defaultState);

  // 将 setState 暴露到模块级，供 useConfirm 调用
  ConfirmDialog._setState = setState;

  const handleConfirm = useCallback(() => {
    state.resolver?.(true);
    setState((s) => ({ ...s, open: false, resolver: null }));
  }, [state.resolver]);

  const handleCancel = useCallback(() => {
    state.resolver?.(false);
    setState((s) => ({ ...s, open: false, resolver: null }));
  }, [state.resolver]);

  return (
    <Dialog open={state.open} onOpenChange={(v) => { if (!v) handleCancel(); }}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle>{state.title}</DialogTitle>
          {state.description && (
            <DialogDescription>{state.description}</DialogDescription>
          )}
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" size="sm" onClick={handleCancel}>
            {state.cancelText}
          </Button>
          <Button
            variant={state.variant === "destructive" ? "destructive" : "default"}
            size="sm"
            onClick={handleConfirm}
          >
            {state.confirmText}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// 模块级引用，ConfirmDialog 挂载时写入
ConfirmDialog._setState = null as ((s: ConfirmState) => void) | null;

/** Hook：返回异步 confirm 函数 */
export function useConfirm() {
  return useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      const setState = ConfirmDialog._setState;
      if (!setState) {
        // 降级：如果 ConfirmDialog 未挂载，回退到原生 confirm
        resolve(window.confirm(options.title));
        return;
      }
      setState({
        ...defaultState,
        ...options,
        open: true,
        resolver: resolve,
      });
    });
  }, []);
}
