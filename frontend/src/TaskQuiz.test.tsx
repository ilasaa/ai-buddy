import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TaskQuiz } from "./components/TaskQuiz";
const response = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status });
function mount() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <TaskQuiz taskId={7} />
    </QueryClientProvider>,
  );
}
test("quiz submits answers, shows persisted attempts and explains errors", async () => {
  let attempts: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        attempts = [
          {
            id: 1,
            score: 0,
            passed: false,
            feedback: [
              { correct: false, explanation: "Сначала запустите тесты" },
            ],
          },
        ];
        return response(attempts[0]);
      }
      return response({
        title: "Code Review",
        passing_score: 1,
        questions: [
          {
            text: "Перед ревью?",
            options: ["Проверить тесты", "Игнорировать CI"],
          },
        ],
        attempts,
      });
    }),
  );
  mount();
  await screen.findByText("Перед ревью?");
  await userEvent.click(screen.getByLabelText("Игнорировать CI"));
  await userEvent.click(
    screen.getByRole("button", { name: "Проверить ответы" }),
  );
  await screen.findByText("Вопрос 1: Сначала запустите тесты");
  expect(fetch).toHaveBeenCalledWith(
    "/api/quizzes/tasks/7",
    expect.objectContaining({ body: JSON.stringify({ answers: [1] }) }),
  );
});
test("quiz displays loading and fetch errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response({ detail: "Тест недоступен" }, 404)),
  );
  mount();
  expect(screen.getByRole("status")).toBeInTheDocument();
  expect(await screen.findByRole("alert")).toHaveTextContent("Тест недоступен");
});
test("quiz displays passed attempt and submit error", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init?: RequestInit) =>
      init?.method === "POST"
        ? response({ detail: "Уже пройден" }, 409)
        : response({
            title: "Git",
            passing_score: 1,
            questions: [{ text: "Ветка?", options: ["Отдельная"] }],
            attempts: [
              {
                id: 1,
                score: 1,
                passed: true,
                feedback: [{ correct: true, explanation: "Верно" }],
              },
            ],
          }),
    ),
  );
  mount();
  await screen.findByText("Попытка №1: 1 — Зачтено");
  await userEvent.click(screen.getByLabelText("Отдельная"));
  await userEvent.click(
    screen.getByRole("button", { name: "Проверить ответы" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("Уже пройден");
});
