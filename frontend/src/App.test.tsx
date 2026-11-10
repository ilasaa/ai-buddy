import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import type { Profile, Task } from "./api";
const profile: Profile = {
  id: 1,
  full_name: "Алексей Иванов",
  email: "intern@example.com",
  role: "intern",
  team: { id: 1, name: "Backend", description: null },
  mentor: {
    id: 2,
    full_name: "Дмитрий Смирнов",
    role: "mentor",
    team: { id: 1, name: "Backend", description: null },
  },
  internship_started_at: "2026-11-01",
};
const task: Task = {
  id: 1,
  title: "Настроить окружение",
  description: "Подготовьте инструменты",
  status: "in_progress",
  due_date: "2026-11-15",
  completed_at: null,
  created_at: "2026-11-01",
};
let loggedIn = false;
let failLogin = false;
let failTasks = false;
let failLogout = false;
let failPatch = false;
let empty = false;
let me: Profile;
let currentTask: Task;
function response(data: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
beforeEach(() => {
  loggedIn = false;
  failLogin = false;
  failTasks = false;
  failLogout = false;
  failPatch = false;
  empty = false;
  me = structuredClone(profile);
  currentTask = { ...task };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/auth/me"))
        return loggedIn
          ? response(me)
          : response({ detail: "Войдите в аккаунт" }, 401);
      if (url.endsWith("/auth/login")) {
        if (failLogin)
          return response({ detail: "Неверный email или пароль" }, 401);
        loggedIn = true;
        return response(me);
      }
      if (url.endsWith("/auth/logout")) {
        if (failLogout) return response({ detail: "Не удалось выйти" }, 500);
        loggedIn = false;
        return response(null, 204);
      }
      if (init?.method === "PATCH") {
        if (failPatch) return response({ detail: "Не удалось обновить" }, 500);
        currentTask = {
          ...currentTask,
          ...(JSON.parse(String(init.body)) as Partial<Task>),
        };
        return response(currentTask);
      }
      if (url.endsWith("/onboarding")) {
        if (failTasks)
          return response({ detail: "Ошибка загрузки задач" }, 500);
        return response({
          tasks: empty ? [] : [currentTask],
          completed: currentTask.status === "done" ? 1 : 0,
          total: empty ? 0 : 1,
          percent: currentTask.status === "done" ? 100 : 0,
        });
      }
      return response({}, 404);
    }),
  );
});
function mount(path = "/") {
  const cache = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return cache;
}
test("private route shows login, password toggle and successful login", async () => {
  mount();
  expect(screen.getByRole("status")).toBeInTheDocument();
  await screen.findByRole("heading", { name: "Рады знакомству 👋" });
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Рабочий email"), "intern@example.com");
  await user.type(screen.getByLabelText("Пароль"), "password");
  await user.click(screen.getByRole("button", { name: "Показать пароль" }));
  expect(screen.getByLabelText("Пароль")).toHaveAttribute("type", "text");
  await user.click(screen.getByRole("button", { name: "Скрыть пароль" }));
  await user.click(screen.getByRole("button", { name: "Войти" }));
  await screen.findByRole("heading", { name: "Привет, Алексей! 👋" });
  expect(screen.getByText("Дмитрий Смирнов")).toBeInTheDocument();
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
});
test("login error", async () => {
  failLogin = true;
  mount("/login");
  await screen.findByLabelText("Рабочий email");
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Рабочий email"), "wrong@example.com");
  await user.type(screen.getByLabelText("Пароль"), "wrong");
  await user.click(screen.getByRole("button", { name: "Войти" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Неверный email или пароль",
  );
});
test("authenticated login redirects and logout removes private content", async () => {
  loggedIn = true;
  mount("/login");
  await screen.findByText("Дмитрий Смирнов");
  await userEvent.click(screen.getByLabelText("Выйти из аккаунта"));
  await screen.findByRole("heading", { name: "Рады знакомству 👋" });
  expect(screen.queryByText("Дмитрий Смирнов")).not.toBeInTheDocument();
});
test("task update refreshes progress and supports descriptions", async () => {
  loggedIn = true;
  mount("/onboarding");
  await screen.findByText("Подготовьте инструменты");
  await userEvent.selectOptions(
    screen.getByLabelText("Статус: Настроить окружение"),
    "done",
  );
  await waitFor(() =>
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "100",
    ),
  );
  await userEvent.selectOptions(
    screen.getByLabelText("Статус: Настроить окружение"),
    "todo",
  );
  await waitFor(() =>
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "0",
    ),
  );
});
test("task failure and retry", async () => {
  loggedIn = true;
  failTasks = true;
  mount();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Ошибка загрузки задач",
  );
  failTasks = false;
  await userEvent.click(
    screen.getByRole("button", { name: "Попробовать снова" }),
  );
  await screen.findByText("Дмитрий Смирнов");
});
test("missing mentor and empty tasks", async () => {
  loggedIn = true;
  empty = true;
  me.mentor = null;
  me.internship_started_at = null;
  mount();
  await screen.findByText(
    "Наставник ещё не назначен. Обратитесь к руководителю команды.",
  );
  expect(
    screen.getByText("Задач пока нет. Обратитесь к наставнику."),
  ).toBeInTheDocument();
  expect(screen.getByText("Не указана")).toBeInTheDocument();
});
test("empty onboarding", async () => {
  loggedIn = true;
  empty = true;
  mount("/onboarding");
  await screen.findByText("Задач пока нет. Наставник поможет составить план.");
});
test("all done dashboard", async () => {
  loggedIn = true;
  currentTask.status = "done";
  mount();
  await screen.findByText("Все задачи выполнены. Поздравляем!");
  expect(screen.getByText("План выполнен")).toBeInTheDocument();
});
test.each(["mentor", "manager"] as const)(
  "minimal %s dashboard",
  async (role) => {
    loggedIn = true;
    me.role = role;
    mount();
    await screen.findByRole("heading", { name: "Здравствуйте, Алексей!" });
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  },
);
test.each([
  ["/assistant", "Ваш AI-buddy уже в пути"],
  ["/requests", "Мои заявки"],
  ["/knowledge", "База знаний"],
  ["/missing", "Страница не найдена"],
])("placeholder %s", async (path, title) => {
  loggedIn = true;
  mount(path);
  await screen.findByRole("heading", { name: title });
  await userEvent.click(
    screen.getByRole("link", { name: /Вернуться на главную/ }),
  );
  await screen.findByRole("heading", { name: "Привет, Алексей! 👋" });
});
test("navigation and mobile menu", async () => {
  loggedIn = true;
  mount();
  await screen.findByText("Дмитрий Смирнов");
  await userEvent.click(screen.getByLabelText("Открыть меню"));
  await userEvent.click(screen.getByLabelText("Закрыть меню"));
  await userEvent.click(screen.getByText("Все задачи"));
  await screen.findByText("Подготовьте инструменты");
});
test("logout and patch errors", async () => {
  loggedIn = true;
  failPatch = true;
  failLogout = true;
  mount("/onboarding");
  await screen.findByText("Подготовьте инструменты");
  await userEvent.selectOptions(
    screen.getByLabelText("Статус: Настроить окружение"),
    "done",
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Не удалось обновить",
  );
  await userEvent.click(screen.getByLabelText("Выйти из аккаунта"));
  await screen.findByText("Не удалось выйти");
});
test("profile server error and retry", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response({ detail: "Сервис недоступен" }, 503)),
  );
  mount();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Сервис недоступен",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Попробовать снова" }),
  );
  expect(fetch).toHaveBeenCalledTimes(2);
});
test("login service error", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response({}, 503)),
  );
  mount("/login");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Не удалось выполнить запрос",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Попробовать снова" }),
  );
});
test("loading state stays visible while awaiting response", async () => {
  let resolve: (response: Response) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<Response>((r) => {
            resolve = r;
          }),
      )
      .mockImplementation(async () => response({ detail: "No session" }, 401)),
  );
  mount();
  expect(screen.getByRole("status")).toHaveTextContent("Загружаем");
  await act(async () => resolve(response({ detail: "No session" }, 401)));
  await screen.findByLabelText("Рабочий email");
});
