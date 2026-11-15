import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Adaptation, type AdaptationData } from "./pages/Adaptation";
import type { Profile } from "./api";
let user: Profile;
let data: AdaptationData;
let fail = false;
let noPeople = false;
let peopleError = false;
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
beforeEach(() => {
  user = {
    id: 1,
    full_name: "Стажёр",
    email: "synthetic@example.test",
    role: "intern",
    team: { id: 1, name: "Backend", description: null },
    mentor: null,
    internship_started_at: null,
  };
  data = {
    plan: {
      id: 1,
      title: "План Backend",
      expectations: "Ожидания руководителя",
      status: "pending_agreement",
      version: 1,
      start_date: "2026-11-01",
      target_date: "2027-01-01",
    },
    goals: [
      {
        id: 1,
        title: "Освоить окружение",
        success_criteria: "Запустить сервис",
        target_date: "2027-01-01",
      },
    ],
    tasks: [
      {
        id: 1,
        title: "Запустить локально",
        description: "Проверить запуск",
        status: "todo",
        verification_type: "review",
        goal_id: 1,
        due_date: "2026-12-01",
        completed_at: null,
        created_at: "2026-11-01",
      },
    ],
    completed: 0,
    total: 1,
    percent: 0,
    next_steps: ["Запустить локально и приложить результат"],
    history: [
      {
        id: 1,
        version: 1,
        action: "send",
        comment: "Проверьте сроки",
        actor_id: 3,
        created_at: "2026-11-01",
      },
    ],
    objectives: [
      { id: 1, title: "Надёжность сервиса", key_results: ["Зелёный CI"] },
    ],
    verifications: [
      {
        id: 1,
        task_id: 1,
        actor_id: 2,
        action: "reject",
        comment: "Добавить тесты",
        evidence: "MR",
      },
    ],
  };
  fail = false;
  noPeople = false;
  peopleError = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/quizzes"))
        return json([{ id: 1, title: "Code Review" }]);
      if (url.endsWith("/auth/me")) return json(user);
      if (url.endsWith("/adaptation/interns"))
        return peopleError
          ? json({ detail: "Ошибка команды" }, 500)
          : json(
              noPeople
                ? []
                : [
                    { id: 1, full_name: "Первый" },
                    { id: 2, full_name: "Второй" },
                  ],
            );
      if (init?.method === "POST") {
        if (fail) return json({ detail: "План изменился" }, 409);
        const body = JSON.parse(String(init.body));
        if (url.endsWith("/agreement") && body.action === "agree")
          data.plan!.status = "active";
        if (url.endsWith("/agreement") && body.action === "send")
          data.plan!.status = "pending_agreement";
        if (url.endsWith("/verification"))
          data.tasks[0].status =
            body.action === "submit"
              ? "submitted"
              : body.action === "approve"
                ? "done"
                : "changes_requested";
        return json(data);
      }
      return fail ? json({ detail: "Ошибка плана" }, 500) : json(data);
    }),
  );
});
function mount() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      <MemoryRouter>
        <AdaptationLoader />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
// Same authenticated profile lifecycle as the protected route.
import { useProfile } from "./session";
function AdaptationLoader() {
  const p = useProfile();
  return p.data ? <Adaptation /> : <p>Ожидание профиля</p>;
}
test("intern reads goals, agrees and submits evidence", async () => {
  mount();
  await screen.findByText("Освоить окружение");
  expect(screen.getByText("Запустить сервис")).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Согласовать план" }),
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("button", { name: "Согласовать план" }),
    ).not.toBeInTheDocument(),
  );
  await userEvent.type(
    screen.getByLabelText("Результат выполнения / ссылка"),
    "MR с тестами",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Отправить результат" }),
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("button", { name: "Отправить результат" }),
    ).not.toBeInTheDocument(),
  );
  expect(fetch).toHaveBeenCalledWith(
    "/api/adaptation/tasks/1/verification",
    expect.objectContaining({
      body: JSON.stringify({ action: "submit", evidence: "MR с тестами" }),
    }),
  );
});
test("intern proposes changes and sees mutation errors", async () => {
  mount();
  await screen.findByText("Освоить окружение");
  await userEvent.type(
    screen.getByLabelText("Комментарий или предложение изменения"),
    "Нужен доступ",
  );
  fail = true;
  await userEvent.click(
    screen.getByRole("button", { name: "Добавить комментарий" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("План изменился");
});
test("manager creates draft, goal, task, OKR and sends plan", async () => {
  user.role = "manager";
  data.plan!.status = "draft";
  mount();
  await screen.findByLabelText("Название плана");
  await userEvent.click(
    screen.getByRole("button", { name: "Сохранить черновик" }),
  );
  await userEvent.type(
    screen.getByLabelText("Цель", { exact: true }),
    "Изучить Git",
  );
  await userEvent.type(
    screen.getByLabelText("Критерии успешности"),
    "Умеет создавать MR",
  );
  await userEvent.type(screen.getByLabelText("Срок цели"), "2026-12-01");
  await userEvent.click(screen.getByRole("button", { name: "Добавить цель" }));
  await userEvent.type(screen.getByLabelText("Название задачи"), "Создать MR");
  await userEvent.type(screen.getByLabelText("Срок задачи"), "2026-12-01");
  await userEvent.selectOptions(
    screen.getByLabelText("Подтверждение"),
    "review",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Назначить задачу" }),
  );
  await userEvent.type(screen.getByLabelText("Цель команды"), "Надёжность");
  await userEvent.type(
    screen.getByLabelText("Ключевые результаты (по одному в строке)"),
    "CI работает",
  );
  await userEvent.type(screen.getByLabelText("Начало периода"), "2026-11-01");
  await userEvent.type(screen.getByLabelText("Конец периода"), "2026-12-01");
  await userEvent.click(screen.getByRole("button", { name: "Добавить OKR" }));
  await userEvent.click(
    screen.getByRole("button", { name: "Отправить на согласование" }),
  );
  await screen.findByRole("button", { name: "Создать новую версию" });
  await userEvent.click(
    screen.getByRole("button", { name: "Создать новую версию" }),
  );
  await userEvent.selectOptions(screen.getByLabelText("Стажёр"), "2");
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith("/api/adaptation/2", expect.anything()),
  );
});
test.each(["Подтвердить выполнение", "Вернуть на доработку"])(
  "mentor reviews assigned task: %s",
  async (name) => {
    user.role = "mentor";
    data.tasks[0].status = "submitted";
    mount();
    await screen.findByText("Освоить окружение");
    await userEvent.type(
      screen.getByLabelText("Комментарий проверки"),
      "Проверено",
    );
    await userEvent.click(screen.getByRole("button", { name }));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "Создать новую версию" }),
    ).not.toBeInTheDocument();
  },
);
test("manager creates first plan for newcomer", async () => {
  user.role = "manager";
  data.plan = null;
  data.goals = [];
  data.tasks = [];
  data.objectives = [];
  mount();
  await screen.findByLabelText("Название плана");
  await userEvent.type(screen.getByLabelText("Название плана"), "План новичка");
  await userEvent.type(
    screen.getByLabelText("Ожидания руководителя"),
    "Освоить процессы",
  );
  await userEvent.type(screen.getByLabelText("Начало"), "2026-11-01");
  await userEvent.type(
    screen.getByLabelText("Срок", { exact: true }),
    "2027-01-01",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Сохранить черновик" }),
  );
  expect(fetch).toHaveBeenCalledWith(
    "/api/adaptation/1/plan",
    expect.objectContaining({ body: expect.stringContaining("План новичка") }),
  );
});
test("empty team and server errors", async () => {
  user.role = "mentor";
  noPeople = true;
  mount();
  await screen.findByText("Нет закреплённых стажёров.");
});
test("team fetch error", async () => {
  user.role = "manager";
  peopleError = true;
  mount();
  expect(await screen.findByRole("alert")).toHaveTextContent("Ошибка команды");
});
test("plan error and retry", async () => {
  fail = true;
  mount();
  expect(await screen.findByRole("alert")).toHaveTextContent("Ошибка плана");
  fail = false;
  await userEvent.click(
    screen.getByRole("button", { name: "Попробовать снова" }),
  );
  await screen.findByText("Освоить окружение");
});

test("manager edits draft goal and task and assigns quiz with server ID", async () => {
  user.role = "manager";
  data.plan!.status = "draft";
  mount();
  await screen.findByLabelText("Название плана");
  await userEvent.click(screen.getByText("Изменить цель"));
  await userEvent.clear(screen.getByLabelText("Название цели"));
  await userEvent.type(
    screen.getByLabelText("Название цели"),
    "Новая формулировка",
  );
  await userEvent.click(screen.getByRole("button", { name: "Сохранить цель" }));
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      "/api/adaptation/1/goals/1",
      expect.objectContaining({ method: "PATCH" }),
    ),
  );
  await userEvent.click(
    screen.getByText("Изменить задачу «Запустить локально»"),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Сохранить задачу" }),
  );
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      "/api/adaptation/1/tasks/1",
      expect.objectContaining({ method: "PATCH" }),
    ),
  );
  await userEvent.type(
    screen.getByLabelText("Название задачи"),
    "Проверить Git",
  );
  await userEvent.type(screen.getByLabelText("Срок задачи"), "2026-12-01");
  await userEvent.selectOptions(screen.getByLabelText("Подтверждение"), "quiz");
  await userEvent.click(
    screen.getByRole("button", { name: "Назначить задачу" }),
  );
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      "/api/adaptation/1/tasks",
      expect.objectContaining({ body: expect.stringContaining('"quiz_id":1') }),
    ),
  );
});
