import { ActionProposals } from "../components/ActionProposals";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "../api";
import { type AccessRequest, permission, statuses } from "../access-api";
import { Feedback } from "../components/Feedback";
import { useProfile } from "../session";

export function Requests() {
  const me = useProfile();
  const cache = useQueryClient();
  const [params, setParams] = useSearchParams();
  const selected = params.get("id");
  const linkedTask = params.get("task_id");
  const prepare = useMutation({
    mutationFn: (body: unknown) =>
      request("/assistant/actions/prepare", "POST", body),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["proposals"] }),
  });
  const [decision, setDecision] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const items = useQuery({
    queryKey: ["requests"],
    queryFn: () => request<AccessRequest[]>("/access-requests"),
    refetchInterval: 10000,
  });
  const detail = useQuery({
    queryKey: ["request", selected],
    queryFn: () => request<AccessRequest>(`/access-requests/${selected}`),
    enabled: !!selected,
    refetchInterval: 10000,
  });
  const mutation = useMutation({
    mutationFn: () =>
      request(`/access-requests/${selected}/${decision}`, "POST", { comment }),
    onSuccess: async () => {
      setDecision(null);
      setComment("");
      await cache.invalidateQueries({ queryKey: ["requests"] });
      await cache.invalidateQueries({ queryKey: ["request"] });
      await cache.invalidateQueries({ queryKey: ["mentor-overview"] });
    },
  });
  if (items.isPending) return <Feedback />;
  if (items.error)
    return (
      <Feedback
        error={items.error}
        retry={() => {
          void items.refetch();
          if (selected) void detail.refetch();
        }}
      />
    );
  return (
    <>
      <h1>Заявки на доступ</h1>
      <p>
        Демонстрационный корпоративный сервис. Согласование не выдаёт реальный
        доступ.
      </p>
      <Link className="text-link" to="/assistant">
        Подготовить заявку через AI-buddy
      </Link>
      {linkedTask && me.data?.role === "intern" && (
        <section className="card">
          <h2>Доступ для задачи №{linkedTask}</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              prepare.mutate({
                ...Object.fromEntries(new FormData(e.currentTarget)),
                task_id: Number(linkedTask),
              });
            }}
          >
            <label>
              Корпоративный ресурс
              <select name="resource">
                <option value="jira">Jira</option>
                <option value="confluence">Confluence</option>
                <option value="gitlab">GitLab</option>
              </select>
            </label>
            <label>
              Проект
              <input name="project_key" defaultValue="BACKEND" required />
            </label>
            <label>
              Права
              <select name="permission">
                <option value="read">Просмотр</option>
                <option value="write">Редактирование</option>
              </select>
            </label>
            <label>
              Обоснование
              <textarea
                name="justification"
                defaultValue="Работа над задачами стажировки"
                required
                minLength={5}
              />
            </label>
            <button disabled={prepare.isPending}>Подготовить черновик</button>
          </form>
          {prepare.error && <p role="alert">{prepare.error.message}</p>}
          <ActionProposals conversationId={null} />
        </section>
      )}
      <div className="request-list">
        {!items.data.length && <p>Заявок пока нет.</p>}
        {items.data.map((item) => (
          <button
            className="card request-row"
            key={item.id}
            onClick={() => {
              setParams({ id: String(item.id) });
              setDecision(null);
            }}
          >
            <strong>
              №{item.id} · {item.resource.toUpperCase()} · {item.project_key}
            </strong>
            <span>
              {permission(item.permission)} · {statuses[item.status]}
            </span>
            <small>
              Создана: {new Date(item.created_at).toLocaleString("ru-RU")} ·
              Обновлена: {new Date(item.updated_at).toLocaleString("ru-RU")}
            </small>
          </button>
        ))}
      </div>
      {detail.error && <p role="alert">{detail.error.message}</p>}
      {detail.data && (
        <section className="card">
          <h2>Заявка №{detail.data.id}</h2>
          <p>
            {detail.data.resource.toUpperCase()} · {detail.data.project_key} ·{" "}
            {permission(detail.data.permission)}
          </p>
          <p>{detail.data.justification}</p>
          {detail.data.task_id && (
            <Link to="/onboarding">
              Связана с задачей №{detail.data.task_id}
            </Link>
          )}
          <p>{statuses[detail.data.status]}</p>
          {detail.data.routing === "awaiting_routing" && (
            <p>
              Согласующий не назначен. Обратитесь к руководителю для
              маршрутизации.
            </p>
          )}
          <h3>История изменений</h3>
          {detail.data.events?.map((event) => (
            <p key={event.id}>
              {new Date(event.created_at).toLocaleString("ru-RU")} ·{" "}
              {event.event_type} · {event.comment}
            </p>
          ))}
          {detail.data.status === "pending" &&
            detail.data.approver_id === me.data?.id && (
              <>
                <label>
                  Комментарий
                  <textarea
                    value={comment}
                    maxLength={1000}
                    onChange={(e) => setComment(e.target.value)}
                  />
                </label>
                <button onClick={() => setDecision("approve")}>
                  Согласовать
                </button>{" "}
                <button onClick={() => setDecision("reject")}>Отклонить</button>
              </>
            )}
          {decision && (
            <div role="group" aria-label="Подтверждение решения">
              <p>
                {decision === "approve" ? "Согласовать" : "Отклонить"} заявку №
                {detail.data.id}?
              </p>
              <button
                className="primary"
                disabled={mutation.isPending}
                onClick={() => mutation.mutate()}
              >
                Подтвердить решение
              </button>{" "}
              <button
                disabled={mutation.isPending}
                onClick={() => setDecision(null)}
              >
                Отмена
              </button>
            </div>
          )}
          {mutation.error && <p role="alert">{mutation.error.message}</p>}
        </section>
      )}
    </>
  );
}
