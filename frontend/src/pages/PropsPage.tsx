import { useParams } from "react-router-dom";
import { EntitiesPage } from "./EntitiesPage";
import { propConfig } from "@/config/entityConfig";
import {
  useProps,
  useCreateProp,
  useUpdateProp,
  useDeleteProp,
} from "@/hooks/useBusiness";

export function PropsPage() {
  const { projectId } = useParams();

  const createMutation = useCreateProp(projectId!);
  const updateMutation = useUpdateProp(projectId!);
  const deleteMutation = useDeleteProp(projectId!);

  return (
    <EntitiesPage
      config={propConfig}
      useEntities={useProps}
      onCreate={(data) => createMutation.mutateAsync(data)}
      onUpdate={(id, payload) => updateMutation.mutateAsync({ id, payload })}
      onDelete={(id) => deleteMutation.mutate(id)}
    />
  );
}
