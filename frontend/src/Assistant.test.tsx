import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Assistant } from "./pages/Assistant";
import { Knowledge } from "./pages/Knowledge";
import { ThemeToggle } from "./components/ThemeToggle";
import type { ChatMessage } from "./assistant-api";
const source = {
  document_id: 1,
  chunk_id: 1,
  title: "Инструкция GitLab",
  source: "demo/gitlab.md",
  score: 0.9,
};
const message: ChatMessage = {
  id: 2,
  role: "assistant",
  content: "Запросите доступ через наставника [1].",
  created_at: "2026-11-10T12:00:00Z",
  sources: [source],
};
let messages: ChatMessage[];
let errorPath: string;
let empty: boolean;
const response = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
beforeEach(() => {
  messages = [];
  errorPath = "";
  empty = false;
  localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (errorPath && url.includes(errorPath))
        return response({ detail: "Лимит или сервис недоступен" }, 503);
      if (url === "/api/assistant/actions") return response([]);
      if (url === "/api/assistant/conversations" && init?.method === "POST")
        return response({ id: 1, title: "Новый диалог" });
      if (url === "/api/assistant/conversations")
        return response(empty ? [] : [{ id: 1, title: "История про GitLab" }]);
      if (url === "/api/assistant/conversations/1") return response(messages);
      if (url === "/api/assistant/chat") {
        const body = JSON.parse(String(init?.body)) as { message: string };
        messages = [
          {
            ...message,
            id: 1,
            role: "user",
            content: body.message,
            sources: [],
          },
          message,
        ];
        return response({
          conversation_id: 1,
          message,
          rag_used: true,
          prompt_tokens: 10,
          completion_tokens: 10,
        });
      }
      if (url === "/api/knowledge/1")
        return response({
          id: 1,
          title: "Инструкция GitLab",
          source: "demo/gitlab.md",
          is_public: false,
          content: "Синтетическая инструкция. Запросите доступ.",
        });
      if (url === "/api/knowledge")
        return response(
          empty
            ? []
            : [
                {
                  id: 1,
                  title: "Инструкция GitLab",
                  source: "demo/gitlab.md",
                  is_public: true,
                  content: "",
                },
              ],
        );
      return response({}, 404);
    }),
  );
});
function mount(path = "/assistant") {
  const cache = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/assistant" element={<Assistant />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/knowledge/:documentId" element={<Knowledge />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return cache;
}
test("chat quick question sends real HTTP and shows source document", async () => {
  mount();
  await screen.findByText("История про GitLab");
  await userEvent.click(
    screen.getByRole("button", { name: "Как получить доступ к GitLab?" }),
  );
  await screen.findByText(message.content);
  expect(screen.getByText("Источники ответа")).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("link", { name: /Инструкция GitLab/ }),
  );
  await screen.findByText("Синтетическая инструкция. Запросите доступ.");
  await userEvent.click(screen.getByRole("link", { name: "Все документы" }));
  await screen.findByText("Общий документ");
});
test("new conversation, send enter and restore history", async () => {
  mount();
  await screen.findByText("История про GitLab");
  await userEvent.click(screen.getByRole("button", { name: "Новый диалог" }));
  const input = screen.getByLabelText("Сообщение AI-buddy");
  await userEvent.type(input, "Какие задачи?{shift>}{enter}{/shift}Уточнение");
  expect(input).toHaveValue("Какие задачи?\nУточнение");
  await userEvent.type(input, "{enter}");
  await screen.findByText(message.content);
  expect(input).toHaveValue("");
  await userEvent.click(
    screen.getByRole("button", { name: "История про GitLab" }),
  );
  await screen.findByText(message.content);
});
test("send button and empty history", async () => {
  empty = true;
  mount();
  await screen.findByText("Ваши диалоги появятся здесь.");
  expect(
    screen.getByRole("button", { name: "Отправить сообщение" }),
  ).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Сообщение AI-buddy"), "Привет");
  await userEvent.click(
    screen.getByRole("button", { name: "Отправить сообщение" }),
  );
  await screen.findByText(message.content);
});
test("chat error preserves text", async () => {
  mount();
  await screen.findByText("История про GitLab");
  errorPath = "/chat";
  await userEvent.type(
    screen.getByLabelText("Сообщение AI-buddy"),
    "Тестовый вопрос",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Отправить сообщение" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Лимит или сервис недоступен",
  );
  expect(screen.getByLabelText("Сообщение AI-buddy")).toHaveValue(
    "Тестовый вопрос",
  );
});
test("conversation loading and errors can retry", async () => {
  errorPath = "/conversations";
  mount();
  await screen.findByRole("alert");
  errorPath = "";
  await userEvent.click(screen.getByRole("button", { name: "Повторить" }));
  await screen.findByText("История про GitLab");
});
test("history errors and new conversation errors", async () => {
  mount();
  await screen.findByText("История про GitLab");
  errorPath = "/conversations/1";
  await userEvent.click(
    screen.getByRole("button", { name: "История про GitLab" }),
  );
  await screen.findByRole("alert");
  errorPath = "";
  await userEvent.click(
    screen.getByRole("button", { name: "Попробовать снова" }),
  );
  await screen.findByText("С чего начнём?");
  errorPath = "/conversations";
  await userEvent.click(screen.getByRole("button", { name: "Новый диалог" }));
  await screen.findByRole("alert");
});
test("knowledge empty and errors", async () => {
  empty = true;
  const cache = mount("/knowledge");
  await screen.findByText(
    "Документы ещё не проиндексированы. Обратитесь к администратору.",
  );
  empty = false;
  errorPath = "/knowledge";
  await act(async () => {
    await cache.invalidateQueries();
  });
  await screen.findByRole("alert");
  errorPath = "";
  await userEvent.click(
    screen.getByRole("button", { name: "Попробовать снова" }),
  );
  await screen.findByText("Инструкция GitLab");
});
test("pending response disables duplicate sends", async () => {
  mount();
  await screen.findByText("История про GitLab");
  let finish: (value: Response) => void = () => {};
  const original = fetch;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) =>
      url.endsWith("/chat")
        ? new Promise<Response>((resolve) => {
            finish = resolve;
          })
        : original(url, init),
    ),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Какие задачи у меня остались?" }),
  );
  await screen.findByText("Запрос отправлен. AI-buddy готовит ответ…");
  expect(
    screen.getByRole("button", { name: "Отправить сообщение" }),
  ).toBeDisabled();
  await act(async () =>
    finish(response({ conversation_id: 1, message, rag_used: false })),
  );
});
test("theme persists and toggles without storing tokens", async () => {
  render(<ThemeToggle />);
  await userEvent.click(
    screen.getByRole("button", { name: "Включить тёмную тему" }),
  );
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem("ai-buddy-theme")).toBe("dark");
  await userEvent.click(
    screen.getByRole("button", { name: "Включить светлую тему" }),
  );
  expect(document.documentElement.dataset.theme).toBe("light");
});

test("Jira starter explains explicit confirmation and accepts natural language", async () => {
  mount();
  await screen.findByText("История про GitLab");
  expect(screen.getByText(/Перед отправкой/)).toHaveTextContent(
    "кнопку подтверждения",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Мне нужен доступ к Jira" }),
  );
  await screen.findByText("Мне нужен доступ к Jira");
  const calls = vi.mocked(fetch).mock.calls;
  const chat = calls.find(([url]) => url === "/api/assistant/chat");
  expect(JSON.parse(String(chat?.[1]?.body)).message).toBe(
    "Мне нужен доступ к Jira",
  );
});
