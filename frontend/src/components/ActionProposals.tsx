import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "../api";
import {
  type AccessRequest,
  type Proposal,
  permission,
  statuses,
} from "../access-api";

export function ActionProposals({
  conversationId,
}: {
  conversationId: number | null;
}) {
  const cache = useQueryClient();
  const [result, setResult] = useState<AccessRequest | null>(null);
  const query = useQuery({
    queryKey: ["proposals"],
    queryFn: () => request<Proposal[]>("/assistant/actions"),
    refetchInterval: 10000,
  });
  const mutation = useMutation({
    mutationFn: async ({ id, action }: { id: string; action: string }) => {
      if (action === "confirm")
        setResult(
          await request<AccessRequest>(
            `/assistant/actions/${id}/confirm`,
            "POST",
          ),
        );
      else await request(`/assistant/actions/${id}/cancel`, "POST");
    },
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["proposals"] });
      await cache.invalidateQueries({ queryKey: ["requests"] });
      await cache.invalidateQueries({ queryKey: ["adaptation"] });
      await cache.invalidateQueries({ queryKey: ["onboarding"] });
    },
  });
  return (
    <div className="action-proposals">
      {query.error && <p role="alert">{query.error.message}</p>}
      {query.data
        ?.filter(
          (p) => p.conversation_id === conversationId && p.state === "prepared",
        )
        .map((p) => (
          <section className="card" key={p.id}>
            <h3>Черновик заявки</h3>
            <p>
              {p.parameters.resource.toUpperCase()} · {p.parameters.project_key}{" "}
              · {permission(p.parameters.permission)}
            </p>
            <p>Причина: {p.parameters.justification}</p>
            {p.parameters.task_id && (
              <p>
                Связанная задача №{p.parameters.task_id}. Задача «Отправить
                заявку» завершится автоматически. Получение доступа требует
                отдельного подтверждения.
              </p>
            )}
            <p>
              Подтверждение до {new Date(p.expires_at).toLocaleString("ru-RU")}.
              Заявка ещё не создана.
            </p>
            <button
              className="primary"
              disabled={
                mutation.isPending ||
                new Date(p.expires_at).getTime() <= Date.now()
              }
              onClick={() => mutation.mutate({ id: p.id, action: "confirm" })}
            >
              Подтвердить создание
            </button>{" "}
            <button
              disabled={mutation.isPending}
              onClick={() => mutation.mutate({ id: p.id, action: "cancel" })}
            >
              Отмена
            </button>
          </section>
        ))}
      {mutation.error && (
        <p role="alert">
          {mutation.error.message} При потере связи повторите подтверждение того
          же черновика.
        </p>
      )}
      {result && (
        <section className="card" role="status">
          <h3>Заявка №{result.id} создана</h3>
          <p>
            {result.resource.toUpperCase()} · {result.project_key} ·{" "}
            {permission(result.permission)}
          </p>
          <p>{statuses[result.status]}</p>
          <Link to={`/requests?id=${result.id}`}>Открыть заявку</Link>
        </section>
      )}
    </div>
  );
}
