import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Requests } from "./pages/Requests";
import { ActionProposals } from "./components/ActionProposals";
import { MentorOverview } from "./components/MentorOverview";
import type { AccessRequest, Proposal } from "./access-api";
const item: AccessRequest = {
  id: 42,
  user_id: 1,
  resource: "jira",
  project_key: "BACKEND",
  permission: "write",
  justification: "Задачи стажировки",
  status: "pending",
  approver_id: 2,
  created_at: "2026-11-11T12:00:00Z",
  updated_at: "2026-11-11T12:00:00Z",
  resolved_at: null,
  routing: "assigned",
  events: [
    {
      id: 1,
      event_type: "created",
      comment: "Ожидает согласования",
      created_at: "2026-11-11T12:00:00Z",
    },
  ],
};
let proposals: Proposal[];
let current: AccessRequest;
let fail: string;
let uid: number;
let empty: boolean;
const response = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
beforeEach(() => {
  current = structuredClone(item);
  fail = "";
  uid = 1;
  empty = false;
  proposals = [
    {
      id: "p1",
      state: "prepared",
      conversation_id: 1,
      expires_at: "2099-01-01T00:00:00Z",
      parameters: {
        resource: "jira",
        project_key: "BACKEND",
        permission: "write",
        justification: "Задачи стажировки",
      },
    },
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (fail && url.includes(fail))
        return response({ detail: "Сервис недоступен" }, 503);
      if (url === "/api/auth/me")
        return response({ id: uid, role: uid === 1 ? "intern" : "mentor" });
      if (url === "/api/access-requests")
        return response(empty ? [] : [current]);
      if (url === "/api/access-requests/42") return response(current);
      if (url.endsWith("/approve") || url.endsWith("/reject")) {
        current.status = url.endsWith("/approve") ? "approved" : "rejected";
        return response(current);
      }
      if (url === "/api/assistant/actions") return response(proposals);
      if (url.endsWith("/confirm")) {
        proposals[0].state = "confirmed";
        return response(current);
      }
      if (url.endsWith("/cancel")) {
        proposals[0].state = "cancelled";
        return response({ state: "cancelled" });
      }
      if (url === "/api/mentor/overview")
        return response({
          interns: [
            {
              id: 1,
              full_name: "Стажёр",
              onboarding: {
                completed: 1,
                total: 2,
                percent: 50,
                tasks: [
                  { id: 1, title: "Изучить Jira", status: "todo" },
                  { id: 2, title: "Вход", status: "done" },
                ],
              },
            },
          ],
          requests: 2,
          pending: 1,
          approved: 1,
          rejected: 0,
        });
      return response({}, 404);
    }),
  );
});
function mount(component: React.ReactNode, path = "/requests?id=42") {
  const cache = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={[path]}>{component}</MemoryRouter>
    </QueryClientProvider>,
  );
}
test("proposal confirms once and shows backend result", async () => {
  mount(<ActionProposals conversationId={1} />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Подтвердить создание" }),
  );
  expect(await screen.findByText("Заявка №42 создана")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Открыть заявку" })).toHaveAttribute(
    "href",
    "/requests?id=42",
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("button", { name: "Подтвердить создание" }),
    ).not.toBeInTheDocument(),
  );
});
test("proposal cancel persists and hides card", async () => {
  mount(<ActionProposals conversationId={1} />);
  await userEvent.click(await screen.findByRole("button", { name: "Отмена" }));
  await waitFor(() =>
    expect(screen.queryByText("Черновик заявки")).not.toBeInTheDocument(),
  );
  expect(proposals[0].state).toBe("cancelled");
});
test("proposal error permits retry of same ID", async () => {
  fail = "/confirm";
  mount(<ActionProposals conversationId={1} />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Подтвердить создание" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "того же черновика",
  );
  fail = "";
  await userEvent.click(
    screen.getByRole("button", { name: "Подтвердить создание" }),
  );
  expect(await screen.findByText("Заявка №42 создана")).toBeInTheDocument();
});
test("expired proposals cannot be confirmed", async () => {
  proposals[0].expires_at = "2020-01-01T00:00:00Z";
  mount(<ActionProposals conversationId={1} />);
  expect(
    await screen.findByRole("button", { name: "Подтвердить создание" }),
  ).toBeDisabled();
});
test("proposal loading error", async () => {
  fail = "/actions";
  mount(<ActionProposals conversationId={1} />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Сервис недоступен",
  );
});
test("intern sees detail and history without approval controls", async () => {
  mount(<Requests />);
  expect(
    await screen.findByRole("heading", { name: "Заявка №42" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/created/)).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Согласовать" }),
  ).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /№42 · JIRA/ }));
});
test.each(["Согласовать", "Отклонить"])(
  "mentor decision %s with confirmation",
  async (label) => {
    uid = 2;
    mount(<Requests />);
    await userEvent.click(await screen.findByRole("button", { name: label }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "Комментарий" }),
      "Проверено",
    );
    expect(current.status).toBe("pending");
    await userEvent.click(
      screen.getByRole("button", { name: "Подтвердить решение" }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: label }),
      ).not.toBeInTheDocument(),
    );
    expect(current.status).toBe(
      label === "Согласовать" ? "approved" : "rejected",
    );
  },
);
test("mentor cancels decision and handles failed approval", async () => {
  uid = 2;
  mount(<Requests />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Согласовать" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Отмена" }));
  expect(
    screen.queryByRole("button", { name: "Подтвердить решение" }),
  ).not.toBeInTheDocument();
  fail = "/approve";
  await userEvent.click(screen.getByRole("button", { name: "Согласовать" }));
  await userEvent.click(
    screen.getByRole("button", { name: "Подтвердить решение" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Сервис недоступен",
  );
});
test("unassigned request displays routing", async () => {
  current.routing = "awaiting_routing";
  current.approver_id = null;
  current.permission = "read";
  mount(<Requests />);
  expect(
    await screen.findByText(/Согласующий не назначен/),
  ).toBeInTheDocument();
});
test("requests error and retry", async () => {
  fail = "access-requests";
  mount(<Requests />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Сервис недоступен",
  );
  fail = "";
  await userEvent.click(
    screen.getByRole("button", { name: "Попробовать снова" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Заявка №42" }),
  ).toBeInTheDocument();
});
test("requests empty and detail error", async () => {
  empty = true;
  fail = "access-requests/42";
  mount(<Requests />);
  expect(await screen.findByText("Заявок пока нет.")).toBeInTheDocument();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Сервис недоступен",
  );
});
test("mentor overview counts and next tasks", async () => {
  mount(<MentorOverview />);
  expect(await screen.findByText("Стажёр")).toBeInTheDocument();
  expect(screen.getByText(/Завершено 1 из 2/)).toBeInTheDocument();
  expect(screen.getByText("Изучить Jira")).toBeInTheDocument();
  expect(screen.queryByText("Вход")).not.toBeInTheDocument();
});
test("mentor overview failure retry", async () => {
  fail = "/mentor/overview";
  mount(<MentorOverview />);
  await screen.findByRole("alert");
  fail = "";
  await userEvent.click(
    screen.getByRole("button", { name: "Попробовать снова" }),
  );
  expect(await screen.findByText("Стажёр")).toBeInTheDocument();
});
