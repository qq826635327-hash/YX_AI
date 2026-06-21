import { useParams } from "react-router-dom";
import { EntitiesPage } from "./EntitiesPage";
import { sceneConfig } from "@/config/entityConfig";
import {
  useScenes,
  useCreateScene,
  useUpdateScene,
  useDeleteScene,
} from "@/hooks/useBusiness";

export function ScenesPage() {
  const { projectId } = useParams();

  const createMutation = useCreateScene(projectId!);
  const updateMutation = useUpdateScene(projectId!);
  const deleteMutation = useDeleteScene(projectId!);

  return (
    <EntitiesPage
      config={sceneConfig}
      useEntities={useScenes}
      onCreate={(data) => createMutation.mutateAsync(data)}
      onUpdate={(id, payload) => updateMutation.mutateAsync({ id, payload })}
      onDelete={(id) => deleteMutation.mutate(id)}
    />
  );
}
