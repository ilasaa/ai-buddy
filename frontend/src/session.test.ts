import { afterEach, expect, test } from "vitest";
import { ApiError } from "./api";
import { queryClient } from "./session";
afterEach(() => queryClient.clear());
test("401 query clears profile and onboarding cache", async () => {
  queryClient.setQueryData(["me"], { id: 1 });
  queryClient.setQueryData(["onboarding"], { tasks: [] });
  await expect(
    queryClient.fetchQuery({
      queryKey: ["protected"],
      queryFn: () => Promise.reject(new ApiError(401, "Expired")),
    }),
  ).rejects.toThrow("Expired");
  expect(queryClient.getQueryData(["me"])).toBeNull();
  expect(queryClient.getQueryData(["onboarding"])).toBeUndefined();
});
test("401 mutation clears profile, other errors preserve it", async () => {
  queryClient.setQueryData(["me"], { id: 1 });
  const mutation = queryClient.getMutationCache().build(queryClient, {
    mutationFn: () => Promise.reject(new ApiError(401, "Expired")),
  });
  await expect(mutation.execute(undefined)).rejects.toThrow("Expired");
  expect(queryClient.getQueryData(["me"])).toBeNull();
  queryClient.setQueryData(["me"], { id: 2 });
  await expect(
    queryClient.fetchQuery({
      queryKey: ["tasks"],
      queryFn: () => Promise.reject(new Error("Network error")),
    }),
  ).rejects.toThrow("Network error");
  expect(queryClient.getQueryData(["me"])).toEqual({ id: 2 });
});

test("expired profile refetch removes old identity to avoid redirect loops", async () => {
  queryClient.setQueryData(["me"], { id: 1 });
  await expect(
    queryClient.fetchQuery({
      queryKey: ["me"],
      staleTime: 0,
      queryFn: () => Promise.reject(new ApiError(401, "Expired")),
    }),
  ).rejects.toThrow("Expired");
  expect(queryClient.getQueryData(["me"])).toBeNull();
});
