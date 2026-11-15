import { Adaptation } from "./pages/Adaptation";
import { Navigate, Route, Routes } from "react-router-dom";
import { Requests } from "./pages/Requests";
import { Assistant } from "./pages/Assistant";
import { Knowledge } from "./pages/Knowledge";
import { ApiError } from "./api";
import { useProfile } from "./session";
import { Layout } from "./components/Layout";
import { Feedback } from "./components/Feedback";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Placeholder } from "./pages/Placeholder";
function Protected() {
  const me = useProfile();
  if (me.isPending) return <Feedback />;
  if (me.error) {
    if (me.error instanceof ApiError && me.error.status === 401)
      return <Navigate to="/login" replace />;
    return <Feedback error={me.error} retry={() => void me.refetch()} />;
  }
  return me.data ? <Layout user={me.data} /> : <Navigate to="/login" replace />;
}
export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protected />}>
        <Route index element={<Dashboard />} />
        <Route path="onboarding" element={<Adaptation />} />
        <Route path="assistant" element={<Assistant />} />
        <Route path="requests" element={<Requests />} />
        <Route path="knowledge" element={<Knowledge />} />
        <Route path="knowledge/:documentId" element={<Knowledge />} />
        <Route
          path="*"
          element={
            <Placeholder
              title="Страница не найдена"
              description="Проверьте адрес или вернитесь в личный кабинет."
            />
          }
        />
      </Route>
    </Routes>
  );
}
