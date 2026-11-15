import { TaskQuiz } from "../components/TaskQuiz";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { request, type Task } from "../api";
import { useProfile } from "../session";
import { Feedback } from "../components/Feedback";
import { statuses } from "../labels";
import { TaskRow } from "../components/TaskRow";
import { Progress } from "../components/Progress";
import { Link } from "react-router-dom";

type Plan = {
  id: number;
  title: string;
  expectations: string;
  status: string;
  version: number;
  start_date: string;
  target_date: string;
};
type Goal = {
  id: number;
  title: string;
  success_criteria: string;
  target_date: string;
  status?: string;
};
export type AdaptationData = {
  questions?: { id: number; question: string; answer: string | null }[];
  metrics?: {
    submitted: number;
    blocked: number;
    overdue: number;
    goals_achieved: number;
    requests_total: number;
    requests_pending: number;
    requests_approved: number;
    requests_rejected: number;
    mean_decision_seconds: number | null;
    assistant_answers: number;
    sources_share: number | null;
  };
  requests?: {
    id: number;
    resource: string;
    status: string;
    task_id: number | null;
  }[];
  plan: Plan | null;
  goals: Goal[];
  tasks: Task[];
  completed: number;
  total: number;
  percent: number;
  next_steps: string[];
  history: {
    id: number;
    version: number;
    action: string;
    comment: string;
    actor_id: number;
    created_at: string;
    actor_role?: string;
    snapshot?: { plan: Plan; goals: Goal[] };
  }[];
  objectives: { id: number; title: string; key_results: string[] }[];
  verifications: {
    id: number;
    task_id: number;
    actor_id: number;
    action: string;
    evidence: string;
    comment: string;
  }[];
};
const planStatuses: Record<string, string> = {
  draft: "Черновик",
  pending_agreement: "Ожидает согласования",
  active: "Согласован",
  completed: "Завершён",
  archived: "В архиве",
};
const actions: Record<string, string> = {
  draft_saved: "Черновик сохранён",
  goal_added: "Цель добавлена",
  task_added: "Задача назначена",
  send: "Отправлен стажёру",
  agree: "Согласован стажёром",
  comment: "Комментарий",
  revise: "Новая версия",
  previous_version: "Предыдущая версия",
  goal_updated: "Цель изменена",
  task_updated: "Задача изменена",
  goal_verified: "Критерии цели подтверждены",
  submit: "Результат отправлен",
  approve: "Подтверждено",
  reject: "Возвращено на доработку",
  self_done: "Самостоятельно выполнено",
  quiz_passed: "Мини-тест пройден",
  synthetic_seed: "Синтетическое начальное состояние",
};
function values(form: HTMLFormElement) {
  return Object.fromEntries(new FormData(form));
}
export function Adaptation() {
  const user = useProfile().data!;
  const [selected, setSelected] = useState<number | null>(null);
  const people = useQuery({
    queryKey: ["adaptation-interns"],
    queryFn: () =>
      request<{ id: number; full_name: string }[]>("/adaptation/interns"),
    enabled: user.role !== "intern",
  });
  const id =
    user.role === "intern" ? user.id : (selected ?? people.data?.[0]?.id);
  const quizzes = useQuery({
    queryKey: ["quiz-catalog"],
    queryFn: () => request<{ id: number; title: string }[]>("/quizzes"),
    enabled: user.role === "mentor",
  });
  const data = useQuery({
    queryKey: ["adaptation", id],
    queryFn: () => request<AdaptationData>(`/adaptation/${id}`),
    enabled: !!id,
  });
  const cache = useQueryClient();
  const mutate = useMutation({
    mutationFn: ({
      path,
      body,
      method,
    }: {
      path: string;
      body: unknown;
      method?: string;
    }) => request<AdaptationData>(path, method ?? "POST", body),
    onSuccess: async (result) => {
      cache.setQueryData(["adaptation", id], result);
      await cache.invalidateQueries({ queryKey: ["onboarding"] });
    },
  });
  const send = (suffix: string, body: unknown) =>
    mutate.mutate({ path: `/adaptation/${id}/${suffix}`, body });
  const patch = (suffix: string, body: unknown) =>
    mutate.mutate({
      path: `/adaptation/${id}/${suffix}`,
      body,
      method: "PATCH",
    });
  const [comment, setComment] = useState("");
  if (user.role !== "intern" && people.isPending) return <Feedback />;
  if (people.error) return <Feedback error={people.error} />;
  if (!id)
    return (
      <section className="card">
        <h1>Адаптация команды</h1>
        <p>Нет закреплённых стажёров.</p>
      </section>
    );
  if (data.isPending) return <Feedback />;
  if (data.error)
    return <Feedback error={data.error} retry={() => void data.refetch()} />;
  const d = data.data!;
  const p = d.plan;
  const mentor = user.role === "mentor";
  const draft = mentor && p?.status === "draft";
  return (
    <>
      <h1>{user.role === "intern" ? "Моя адаптация" : "Адаптация команды"}</h1>
      {user.role !== "intern" && (
        <label>
          Стажёр{" "}
          <select
            value={id}
            disabled={mutate.isPending}
            onChange={(e) => {
              setSelected(Number(e.target.value));
              setComment("");
            }}
          >
            {people.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}
              </option>
            ))}
          </select>
        </label>
      )}
      {mutate.error && (
        <p role="alert" className="error">
          {mutate.error.message}
        </p>
      )}
      <fieldset disabled={mutate.isPending} className="adaptation-fields">
        <Progress data={d} />
        {d.metrics && (
          <section className="card">
            <h2>Обзор адаптации</h2>
            <p>
              На проверке: {d.metrics.submitted} · Просрочено:{" "}
              {d.metrics.overdue} · Заблокировано: {d.metrics.blocked} ·
              Достигнутых целей: {d.metrics.goals_achieved}
            </p>
            <p>
              Заявок: {d.metrics.requests_total} · Ожидают:{" "}
              {d.metrics.requests_pending} · Согласованы:{" "}
              {d.metrics.requests_approved} · Отклонены:{" "}
              {d.metrics.requests_rejected}
            </p>
            <p>
              Среднее время решения:{" "}
              {d.metrics.mean_decision_seconds === null
                ? "пока нет решений"
                : `${d.metrics.mean_decision_seconds} с`}
            </p>
            <p>
              Ответов ассистента: {d.metrics.assistant_answers}. Доля ответов с
              источниками:{" "}
              {d.metrics.sources_share === null
                ? "нет ответов"
                : `${d.metrics.sources_share}%`}
              . Активность чата сама по себе не доказывает пользу.
            </p>
          </section>
        )}
        {!!d.requests?.length && (
          <section className="card">
            <h2>Заявки стажёра</h2>
            {d.requests.map((r) => (
              <p key={r.id}>
                <Link to={`/requests?id=${r.id}`}>
                  №{r.id} · {r.resource}
                </Link>{" "}
                ·{" "}
                {{
                  pending: "Ожидает решения",
                  approved: "Согласована, доступ ещё не выдан",
                  rejected: "Отклонена",
                }[r.status] ?? r.status}
                {r.task_id ? ` · Задача №${r.task_id}` : ""}
              </p>
            ))}
          </section>
        )}
        <section className="card">
          <h2>План и ожидания</h2>
          {p ? (
            <>
              <h3>{p.title}</h3>
              <p>
                {planStatuses[p.status]} · Версия {p.version} · {p.start_date} —{" "}
                {p.target_date}
              </p>
              <p>{p.expectations}</p>
              <p>
                Подтверждено задач: {d.completed} из {d.total} ({d.percent}%)
              </p>
            </>
          ) : (
            <p>План ещё не создан. Обсудите ожидания с наставником.</p>
          )}
          {mentor && (!p || draft) && (
            <form
              key={`${id}-${p?.version ?? 0}`}
              onSubmit={(e) => {
                e.preventDefault();
                send("plan", {
                  ...values(e.currentTarget),
                  version: p?.version ?? 0,
                });
              }}
            >
              <label>
                Название плана
                <input
                  name="title"
                  defaultValue={p?.title}
                  required
                  minLength={3}
                />
              </label>
              <label>
                Ожидания наставника
                <textarea
                  name="expectations"
                  defaultValue={p?.expectations}
                  required
                  minLength={3}
                />
              </label>
              <label>
                Начало
                <input
                  type="date"
                  name="start_date"
                  defaultValue={p?.start_date}
                  required
                />
              </label>
              <label>
                Срок
                <input
                  type="date"
                  name="target_date"
                  defaultValue={p?.target_date}
                  required
                />
              </label>
              <button>Сохранить черновик</button>
            </form>
          )}
          {p && (
            <>
              <label>
                Комментарий или предложение изменения
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                />
              </label>
              <button
                onClick={() =>
                  send("agreement", {
                    action: "comment",
                    version: p.version,
                    comment,
                  })
                }
              >
                Добавить комментарий
              </button>
              {draft && (
                <button
                  onClick={() =>
                    send("agreement", { action: "send", version: p.version })
                  }
                >
                  Отправить на согласование
                </button>
              )}
              {mentor && p.status !== "draft" && (
                <button
                  onClick={() =>
                    send("agreement", { action: "revise", version: p.version })
                  }
                >
                  Создать новую версию
                </button>
              )}
              {user.role === "intern" && p.status === "pending_agreement" && (
                <button
                  onClick={() =>
                    send("agreement", {
                      action: "agree",
                      version: p.version,
                      comment,
                    })
                  }
                >
                  Согласовать план
                </button>
              )}
            </>
          )}
        </section>
        <section className="card">
          <h2>Следующие шаги</h2>
          {d.next_steps.map((s, i) => (
            <p key={i}>{s}</p>
          ))}
        </section>
        <section className="card">
          <h2>Цели и критерии успешности</h2>
          {d.goals.map((g) => (
            <article key={g.id}>
              <h3>{g.title}</h3>
              <p>{g.success_criteria}</p>
              <small>
                Срок: {g.target_date} ·{" "}
                {g.status === "achieved"
                  ? "Достигнута и подтверждена"
                  : "В работе"}
              </small>
              {draft && (
                <details>
                  <summary>Изменить цель</summary>
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      patch(`goals/${g.id}`, {
                        ...values(e.currentTarget),
                        version: p!.version,
                      });
                    }}
                  >
                    <label>
                      Название цели
                      <input
                        name="title"
                        defaultValue={g.title}
                        required
                        minLength={3}
                      />
                    </label>
                    <label>
                      Критерии цели
                      <textarea
                        name="success_criteria"
                        defaultValue={g.success_criteria}
                        required
                        minLength={3}
                      />
                    </label>
                    <label>
                      Новый срок цели
                      <input
                        name="target_date"
                        type="date"
                        defaultValue={g.target_date}
                        required
                      />
                    </label>
                    <button>Сохранить цель</button>
                  </form>
                </details>
              )}
              {mentor && p?.status === "active" && g.status !== "achieved" && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    send(`goals/${g.id}/verify`, {
                      action: "approve",
                      ...values(e.currentTarget),
                    });
                  }}
                >
                  <label>
                    Подтверждение критериев
                    <textarea name="evidence" required />
                  </label>
                  <button>Подтвердить достижение цели</button>
                </form>
              )}
            </article>
          ))}
          {draft && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                send("goals", {
                  ...values(e.currentTarget),
                  version: p!.version,
                });
              }}
            >
              <label>
                Цель
                <input name="title" required minLength={3} />
              </label>
              <label>
                Критерии успешности
                <textarea name="success_criteria" required minLength={3} />
              </label>
              <label>
                Срок цели
                <input type="date" name="target_date" required />
              </label>
              <button>Добавить цель</button>
            </form>
          )}
        </section>
        <section className="card">
          <h2>Задачи и результаты</h2>
          {!d.tasks.length && (
            <p>Задач пока нет. Наставник поможет составить план.</p>
          )}
          {d.tasks.map((t) => (
            <TaskReview
              key={t.id}
              task={t}
              role={user.role}
              busy={mutate.isPending}
              act={(body) =>
                mutate.mutate({
                  path: `/adaptation/tasks/${t.id}/verification`,
                  body,
                })
              }
            />
          ))}
          {draft &&
            d.tasks.map((t) => (
              <details key={t.id}>
                <summary>Изменить задачу «{t.title}»</summary>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const v = values(e.currentTarget);
                    patch(`tasks/${t.id}`, {
                      ...v,
                      request_resource:
                        v.verification_type === "request"
                          ? String(v.request_resource)
                          : null,
                      quiz_id:
                        v.verification_type === "quiz"
                          ? Number(v.quiz_id)
                          : null,
                      goal_id: Number(v.goal_id),
                      version: p!.version,
                    });
                  }}
                >
                  <label>
                    Новое название задачи
                    <input
                      name="title"
                      defaultValue={t.title}
                      required
                      minLength={3}
                    />
                  </label>
                  <label>
                    Описание задачи
                    <textarea
                      name="description"
                      defaultValue={t.description ?? ""}
                    />
                  </label>
                  <label>
                    Связать с целью
                    <select
                      name="goal_id"
                      defaultValue={t.goal_id ?? d.goals[0]?.id}
                    >
                      {d.goals.map((g) => (
                        <option key={g.id} value={g.id}>
                          {g.title}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Новый срок задачи
                    <input
                      type="date"
                      name="due_date"
                      defaultValue={t.due_date ?? ""}
                      required
                    />
                  </label>
                  <label>
                    Способ подтверждения
                    <select
                      name="verification_type"
                      defaultValue={t.verification_type ?? "self"}
                    >
                      <option value="self">Самостоятельно</option>
                      <option value="review">Проверка результата</option>
                      <option value="quiz">Мини-тест</option>
                      <option value="request">Отправка заявки</option>
                    </select>
                  </label>
                  <label>
                    Мини-тест
                    <select
                      name="quiz_id"
                      defaultValue={t.quiz_id ?? undefined}
                    >
                      {quizzes.data?.map((q) => (
                        <option key={q.id} value={q.id}>
                          {q.title}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Ресурс заявки
                    <select
                      name="request_resource"
                      defaultValue={t.request_resource ?? "jira"}
                    >
                      <option value="jira">Jira</option>
                      <option value="confluence">Confluence</option>
                      <option value="gitlab">GitLab</option>
                    </select>
                  </label>
                  <button>Сохранить задачу</button>
                </form>
              </details>
            ))}
          {draft && d.goals.length > 0 && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const v = values(e.currentTarget);
                send("tasks", {
                  ...v,
                  request_resource:
                    v.verification_type === "request"
                      ? String(v.request_resource)
                      : null,
                  quiz_id:
                    v.verification_type === "quiz" ? Number(v.quiz_id) : null,
                  goal_id: Number(v.goal_id),
                  version: p!.version,
                });
              }}
            >
              <label>
                Название задачи
                <input name="title" required minLength={3} />
              </label>
              <label>
                Цель задачи
                <select name="goal_id">
                  {d.goals.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.title}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Срок задачи
                <input type="date" name="due_date" required />
              </label>
              <label>
                Подтверждение
                <select name="verification_type">
                  <option value="self">Самостоятельно</option>
                  <option value="review">Проверка наставником</option>
                  <option value="quiz">Мини-тест</option>
                  <option value="request">Отправка заявки</option>
                </select>
              </label>
              <label>
                Мини-тест (только для соответствующего типа)
                <select name="quiz_id">
                  {quizzes.data?.map((q) => (
                    <option key={q.id} value={q.id}>
                      {q.title}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Ресурс для задачи отправки заявки
                <select name="request_resource">
                  <option value="jira">Jira</option>
                  <option value="confluence">Confluence</option>
                  <option value="gitlab">GitLab</option>
                </select>
              </label>
              <button>Назначить задачу</button>
            </form>
          )}
        </section>
        <section className="card">
          <h2>OKR команды</h2>
          {d.objectives.length ? (
            d.objectives.map((o) => (
              <article key={o.id}>
                <h3>{o.title}</h3>
                <ul>
                  {o.key_results.map((k, i) => (
                    <li key={i}>{k}</li>
                  ))}
                </ul>
              </article>
            ))
          ) : (
            <p>OKR пока не указаны наставником.</p>
          )}
          {mentor && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const v = values(e.currentTarget);
                send("objectives", {
                  ...v,
                  key_results: String(v.key_results)
                    .split("\n")
                    .filter(Boolean),
                });
              }}
            >
              <label>
                Цель команды
                <input name="title" required minLength={3} />
              </label>
              <label>
                Ключевые результаты (по одному в строке)
                <textarea name="key_results" required />
              </label>
              <label>
                Начало периода
                <input type="date" name="period_start" required />
              </label>
              <label>
                Конец периода
                <input type="date" name="period_end" required />
              </label>
              <button>Добавить OKR</button>
            </form>
          )}
        </section>
        <section className="card">
          <h2>Обращения к наставнику</h2>
          {d.questions?.map((q) => (
            <article key={q.id}>
              <p>{q.question}</p>
              <p>{q.answer ?? "Ожидает ответа наставника"}</p>
              {user.role === "mentor" && !q.answer && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    send(`questions/${q.id}/answer`, values(e.currentTarget));
                  }}
                >
                  <label>
                    Ответ наставника
                    <textarea name="text" required minLength={3} />
                  </label>
                  <button>Отправить ответ</button>
                </form>
              )}
            </article>
          ))}
          {user.role === "intern" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                send("questions", values(e.currentTarget));
              }}
            >
              <label>
                Вопрос наставнику
                <textarea name="text" required minLength={3} />
              </label>
              <button>Отправить вопрос наставнику</button>
            </form>
          )}
          <h2>История согласования</h2>
          {d.history.map((h) => (
            <div key={h.id}>
              Версия {h.version} · {actions[h.action] ?? h.action} ·
              пользователь №{h.actor_id} ·{" "}
              {new Date(h.created_at).toLocaleString("ru-RU")} {h.comment}
              {h.snapshot?.plan && (
                <details>
                  <summary>Показать сохранённую версию</summary>
                  <h3>{h.snapshot.plan.title}</h3>
                  <p>{h.snapshot.plan.expectations}</p>
                  {h.snapshot.goals.map((g) => (
                    <p key={g.id}>
                      {g.title}: {g.success_criteria}
                    </p>
                  ))}
                </details>
              )}
            </div>
          ))}
          <h2>История проверки задач</h2>
          {d.verifications.map((v) => (
            <p key={v.id}>
              Задача №{v.task_id} · {actions[v.action] ?? v.action} ·
              пользователь №{v.actor_id}: {v.evidence} {v.comment}
            </p>
          ))}
        </section>
      </fieldset>
    </>
  );
}
function TaskReview({
  task: t,
  role,
  busy,
  act,
}: {
  task: Task;
  role: string;
  busy: boolean;
  act: (body: unknown) => void;
}) {
  const [text, setText] = useState("");
  const [finishing, setFinishing] = useState(false);
  return (
    <article className="adaptation-task">
      <TaskRow
        task={t}
        onComplete={() => setFinishing(true)}
        editable={
          role === "intern" &&
          t.status !== "submitted" &&
          !(t.status === "done" && (t.verification_type ?? "self") !== "self")
        }
      />
      <p>
        {statuses[t.status]} ·{" "}
        {t.verification_type === "review"
          ? "Проверка результата"
          : t.verification_type === "quiz"
            ? "Мини-тест"
            : t.verification_type === "request"
              ? "Завершается после отправки заявки"
              : "Самостоятельное подтверждение"}{" "}
        · Срок: {t.due_date ?? "не указан"}
      </p>
      <p>{t.evidence}</p>
      {role === "intern" &&
        t.verification_type !== "request" &&
        /доступ/i.test(t.title) &&
        t.status === "in_progress" && (
          <Link className="text-link" to={`/requests?task_id=${t.id}`}>
            Подготовить заявку на доступ для задачи
          </Link>
        )}
      <p>{t.review_comment}</p>
      {role === "intern" &&
        t.verification_type === "quiz" &&
        (finishing || t.status === "done") && (
          <TaskQuiz taskId={t.id} completed={t.status === "done"} />
        )}
      {((role === "intern" &&
        t.verification_type === "review" &&
        finishing &&
        t.status === "in_progress") ||
        (role !== "intern" && t.status === "submitted")) && (
        <>
          <label>
            {role === "intern"
              ? "Результат выполнения / ссылка"
              : "Комментарий проверки"}
            <textarea value={text} onChange={(e) => setText(e.target.value)} />
          </label>
          {role === "intern" ? (
            <button
              disabled={busy}
              onClick={() => act({ action: "submit", evidence: text })}
            >
              Отправить на проверку
            </button>
          ) : (
            <>
              <button
                disabled={busy}
                onClick={() => act({ action: "approve", comment: text })}
              >
                Подтвердить выполнение
              </button>
              <button
                disabled={busy}
                onClick={() => act({ action: "reject", comment: text })}
              >
                Вернуть на доработку
              </button>
            </>
          )}
        </>
      )}
    </article>
  );
}
