import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { EntityConfig } from "@/config/entityConfig";
import type { BaseEntity } from "@/types";

interface EntityEditDialogProps<T extends BaseEntity> {
  config: EntityConfig<T>;
  open: boolean;
  entity: T | null;
  onOpenChange: (v: boolean) => void;
  onSubmit: (data: Partial<T>) => void;
}

export function EntityEditDialog<T extends BaseEntity>({
  config,
  open,
  entity,
  onOpenChange,
  onSubmit,
}: EntityEditDialogProps<T>) {
  const [formData, setFormData] = useState<Record<string, any>>({});

  useEffect(() => {
    if (open) {
      setFormData(config.getInitialValues(entity));
    }
  }, [open, entity, config]);

  const handleSubmit = () => {
    const data = config.buildSubmitData(formData);
    onSubmit(data);
  };

  const updateField = (name: string, value: any) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{config.getDialogTitle(entity)}</DialogTitle>
          <DialogDescription>{config.getDialogDescription(entity)}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          {config.editFields.map((field) => (
            <div key={field.name} className="space-y-2">
              <Label>{field.label}</Label>
              {field.type === "text" && (
                <Input
                  value={(formData[field.name] ?? "") as string}
                  onChange={(e) => updateField(field.name, e.target.value)}
                  placeholder={field.placeholder}
                />
              )}
              {field.type === "textarea" && (
                <Textarea
                  value={(formData[field.name] ?? "") as string}
                  onChange={(e) => updateField(field.name, e.target.value)}
                  placeholder={field.placeholder}
                  rows={field.rows ?? 3}
                />
              )}
              {field.type === "tabs" && field.options && (
                <Tabs
                  value={(formData[field.name] ?? field.options[0].value) as string}
                  onValueChange={(v) => updateField(field.name, v)}
                >
                  <TabsList>
                    {field.options.map((opt) => (
                      <TabsTrigger key={opt.value} value={opt.value}>
                        {opt.label}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>
              )}
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            disabled={!((formData["name"] as string) || "").trim()}
            onClick={handleSubmit}
          >
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
