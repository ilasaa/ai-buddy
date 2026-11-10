import type { Role, Status } from "./api";
export const roles: Record<Role, string> = {
  intern: "Стажёр",
  mentor: "Наставник",
  manager: "Руководитель",
};
export const statuses: Record<Status, string> = {
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
