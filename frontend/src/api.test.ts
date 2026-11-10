import { expect, test, vi } from "vitest";
import { request, ApiError } from "./api";
test("request handles invalid error JSON", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("unavailable", { status: 502 })),
  );
  await expect(request("/auth/me")).rejects.toBeInstanceOf(ApiError);
});
test("request sends credentials, custom CSRF header and JSON", async () => {
  const mock = vi.fn(async () => new Response("{}"));
  vi.stubGlobal("fetch", mock);
  await request("/auth/login", "POST", { email: "test" });
  expect(mock).toHaveBeenCalledWith(
    "/api/auth/login",
    expect.objectContaining({
      credentials: "include",
      headers: expect.objectContaining({ "X-Requested-With": "AI-buddy" }),
      body: '{"email":"test"}',
    }),
  );
});

test("network errors are safe and localized", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }),
  );
  await expect(request("/assistant/conversations")).rejects.toThrow(
    "Не удалось связаться с сервером",
  );
});
