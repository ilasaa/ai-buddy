import type { Role, Status } from "./api";
export const roles: Record<Role, string> = {
  intern: "Стажёр",
  mentor: "Наставник",
};
export const statuses: Record<Status, string> = {
  submitted: "На проверке",
  changes_requested: "На доработке",
  blocked: "Заблокировано",
  todo: "Не начато",
  in_progress: "В процессе",
  done: "Выполнено",
};
export const date = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat("ru-RU", {
        day: "numeric",
        month: "long",
        year: "numeric",
      }).format(new Date(value))
    : "Не указана";
