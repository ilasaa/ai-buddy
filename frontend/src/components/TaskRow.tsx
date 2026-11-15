import { Link } from "react-router-dom";
import { Check } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { request, type Status, type Task } from "../api";
import { statuses, date } from "../labels";
export function TaskRow({
  task,
  editable = false,
  onComplete,
}: {
  task: Task;
  editable?: boolean;
  onComplete?: () => void;
}) {
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: (status: Status) =>
      request<Task>(`/users/me/onboarding/${task.id}`, "PATCH", { status }),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["onboarding"] });
      await cache.invalidateQueries({ queryKey: ["adaptation"] });
    },
  });
  return (
    <div className="task-row">
      <span className={`task-icon ${task.status}`}>
        {task.status === "done" ? (
          <Check size={17} />
        ) : task.status === "in_progress" ? (
          <span className="inner-dot" />
        ) : null}
      </span>
      <div className="task-main">
        <strong>{task.title}</strong>
        {editable && task.description && <p>{task.description}</p>}
        <small>
          {task.due_date ? `До ${date(task.due_date)}` : "Без срока"}
        </small>
        {mutation.error && (
          <p className="error" role="alert">
            {mutation.error.message}
          </p>
        )}
      </div>
      <div className="task-actions">
        <span className={`status ${task.status}`}>{statuses[task.status]}</span>
        {editable &&
          ["todo", "blocked", "changes_requested"].includes(task.status) && (
            <button
              disabled={mutation.isPending}
              aria-label={`Приступить: ${task.title}`}
              onClick={() => mutation.mutate("in_progress")}
            >
              {task.status === "todo" ? "Приступить" : "Продолжить"}
            </button>
          )}
        {editable &&
          task.status === "in_progress" &&
          ((task.verification_type ?? "self") === "self" ? (
            <button
              disabled={mutation.isPending}
              aria-label={`Завершить: ${task.title}`}
              onClick={() => mutation.mutate("done")}
            >
              Завершить
            </button>
          ) : task.verification_type === "request" ? (
            <Link
              className="text-link"
              to={`/requests?task_id=${task.id}&resource=${task.request_resource ?? "jira"}`}
            >
              Отправить заявку
            </Link>
          ) : (
            <button disabled={mutation.isPending} onClick={onComplete}>
              {task.verification_type === "quiz"
                ? "Пройти мини-тест"
                : "Завершить"}
            </button>
          ))}
      </div>
    </div>
  );
}
