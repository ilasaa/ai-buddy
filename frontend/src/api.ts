export type Role = "intern" | "mentor" | "manager";
export type Status = "todo" | "in_progress" | "done";
export interface Team {
  id: number;
  name: string;
  description: string | null;
}
export interface Profile {
  id: number;
  full_name: string;
  email: string;
  role: Role;
  team: Team;
  mentor: { id: number; full_name: string; role: Role; team: Team } | null;
  internship_started_at: string | null;
}
export interface Task {
  id: number;
  title: string;
  description: string | null;
  status: Status;
  due_date: string | null;
  completed_at: string | null;
  created_at: string;
}
export interface Onboarding {
  tasks: Task[];
  completed: number;
  total: number;
  percent: number;
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "AI-buddy",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(
      0,
      "Не удалось связаться с сервером. Проверьте соединение и повторите запрос.",
    );
  }
  if (!response.ok) {
    const data = (await response.json().catch(() => null)) as {
      detail?: unknown;
    } | null;
    throw new ApiError(
      response.status,
      typeof data?.detail === "string"
        ? data.detail
        : "Не удалось выполнить запрос. Попробуйте ещё раз.",
    );
  }
  return response.status === 204
    ? (undefined as T)
    : (response.json() as Promise<T>);
}
