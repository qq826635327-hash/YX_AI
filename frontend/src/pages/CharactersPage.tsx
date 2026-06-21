import { useParams } from "react-router-dom";
import { EntitiesPage } from "./EntitiesPage";
import { characterConfig } from "@/config/entityConfig";
import {
  useCharacters,
  useCreateCharacter,
  useUpdateCharacter,
  useDeleteCharacter,
} from "@/hooks/useBusiness";

export function CharactersPage() {
  const { projectId } = useParams();

  const createMutation = useCreateCharacter(projectId!);
  const updateMutation = useUpdateCharacter(projectId!);
  const deleteMutation = useDeleteCharacter(projectId!);

  return (
    <EntitiesPage
      config={characterConfig}
      useEntities={useCharacters}
      onCreate={(data) => createMutation.mutateAsync(data)}
      onUpdate={(id, payload) => updateMutation.mutateAsync({ id, payload })}
      onDelete={(id) => deleteMutation.mutate(id)}
    />
  );
}
