import { Check } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { request, type Status, type Task } from "../api";
import { statuses, date } from "../labels";
export function TaskRow({
  task,
  editable = false,
}: {
  task: Task;
  editable?: boolean;
}) {
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: (status: Status) =>
      request<Task>(`/users/me/onboarding/${task.id}`, "PATCH", { status }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["onboarding"] }),
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
      {editable ? (
        <select
          aria-label={`Статус: ${task.title}`}
          value={task.status}
          disabled={mutation.isPending}
          onChange={(e) => mutation.mutate(e.target.value as Status)}
        >
          {Object.entries(statuses).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      ) : (
        <span className={`status ${task.status}`}>{statuses[task.status]}</span>
      )}
    </div>
  );
}
