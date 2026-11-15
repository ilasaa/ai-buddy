import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { request, type Onboarding } from "../api";
import { Feedback } from "./Feedback";

export function MentorOverview() {
  const query = useQuery({
    queryKey: ["mentor-overview"],
    queryFn: () =>
      request<{
        interns: { id: number; full_name: string; onboarding: Onboarding }[];
        requests: number;
        pending: number;
        approved: number;
        rejected: number;
      }>("/mentor/overview"),
    refetchInterval: 10000,
  });
  if (query.isPending) return <Feedback />;
  if (query.error)
    return <Feedback error={query.error} retry={() => void query.refetch()} />;
  const data = query.data;
  return (
    <>
      <section className="card">
        <h2>Адаптация команды</h2>
        <p>
          Заявок: {data.requests} · Ожидают: {data.pending} · Согласованы:{" "}
          {data.approved} · Отклонены: {data.rejected}
        </p>
        <p>Показатели рассчитаны из данных демонстрационной системы.</p>
        <Link to="/requests">Перейти к согласованию</Link>
      </section>
      {data.interns.map((person) => (
        <section className="card" key={person.id}>
          <h3>{person.full_name}</h3>
          <p>
            Завершено {person.onboarding.completed} из {person.onboarding.total}{" "}
            задач · {person.onboarding.percent}%
          </p>
          <h4>Следующие задачи</h4>
          {person.onboarding.tasks
            .filter((t) => t.status !== "done")
            .slice(0, 3)
            .map((t) => (
              <p key={t.id}>{t.title}</p>
            ))}
        </section>
      ))}
    </>
  );
}
