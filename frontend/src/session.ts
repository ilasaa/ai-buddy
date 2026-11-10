import {
  QueryClient,
  QueryCache,
  MutationCache,
  useQuery,
} from "@tanstack/react-query";
import { ApiError, request, type Profile } from "./api";
function sessionError(error: Error) {
  if (error instanceof ApiError && error.status === 401) {
    queryClient.setQueryData(["me"], null);
    queryClient.removeQueries({ queryKey: ["onboarding"] });
  }
}
export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: sessionError }),
  mutationCache: new MutationCache({ onError: sessionError }),
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: true, staleTime: 15000 },
  },
});
export function useProfile() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => request<Profile>("/auth/me"),
  });
}
