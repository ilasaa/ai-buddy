import { Navigate, Route, Routes } from "react-router-dom";
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
        <Route path="onboarding" element={<Dashboard all />} />
        <Route
          path="assistant"
          element={
            <Placeholder
              title="Ваш AI-buddy уже в пути"
              description="ИИ-помощник появится в следующей версии. Чат, поиск по знаниям и корпоративные инструменты ещё не подключены."
            />
          }
        />
        <Route
          path="requests"
          element={
            <Placeholder
              title="Мои заявки"
              description="Создание и отслеживание заявок появится после подключения корпоративных сервисов."
            />
          }
        />
        <Route
          path="knowledge"
          element={
            <Placeholder
              title="База знаний"
              description="Здесь появятся материалы для знакомства с командой. Корпоративные источники ещё не подключены."
            />
          }
        />
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
