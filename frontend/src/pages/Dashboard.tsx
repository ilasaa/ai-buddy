import { MentorOverview } from "../components/MentorOverview";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ChevronRight, Layers, Sparkles } from "lucide-react";
import { request, type Onboarding } from "../api";
import { roles, date } from "../labels";
import { useProfile } from "../session";
import { Feedback } from "../components/Feedback";
import { Progress } from "../components/Progress";
import { TaskRow } from "../components/TaskRow";
export function Dashboard({ all = false }: { all?: boolean }) {
  const me = useProfile();
  const user = me.data!;
  const tasks = useQuery({
    queryKey: ["onboarding"],
    queryFn: () => request<Onboarding>("/users/me/onboarding"),
    enabled: user.role === "intern",
  });
  if (user.role !== "intern")
    return (
      <>
        <span className="eyebrow">ЛИЧНОЕ ПРОСТРАНСТВО</span>
        <h1>Здравствуйте, {user.full_name.split(" ")[0]}!</h1>
        <section className="card">
          <h2>{roles[user.role]}</h2>
          <p>Ваша команда: {user.team.name}</p>
          <Link to="/onboarding" className="text-link">
            Открыть планы адаптации и задачи на проверку
          </Link>
          <MentorOverview />
        </section>
      </>
    );
  if (tasks.isPending) return <Feedback />;
  if (tasks.error)
    return <Feedback error={tasks.error} retry={() => void tasks.refetch()} />;
  const data = tasks.data;
  const next = data.tasks.filter((t) => t.status !== "done").slice(0, 3);
  const day = user.internship_started_at
    ? Math.floor(
        (Date.now() - new Date(user.internship_started_at).getTime()) /
          86400000,
      ) + 1
    : null;
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            {all ? "ВАШ ПЕРСОНАЛЬНЫЙ ПЛАН" : "РАСТЁМ ВМЕСТЕ, ШАГ ЗА ШАГОМ"}
          </span>
          <h1>
            {all ? "Моя адаптация" : `Привет, ${user.full_name.split(" ")[0]}!`}
          </h1>
          <p>
            {all
              ? "Ваши задачи, первые достижения и следующие шаги."
              : `Добро пожаловать в команду ${user.team.name}. Здесь начинается ваш путь.`}
          </p>
        </div>
        <span className="day-badge">
          <span className="green-dot" />
          {day && day > 0 ? `День ${day} в команде` : "Новый этап"}
        </span>
      </div>
      <div className="overview-grid">
        <Progress data={data} />
        <section className="assistant-card">
          <div className="assistant-top">
            <span className="assistant-icon">
              <Sparkles size={24} />
            </span>
            <span className="assistant-tag">ВАШ ИИ-НАСТАВНИК</span>
          </div>
          <h2>Спроси AI-buddy</h2>
          <p>
            Вопросы о задачах, инструментах и команде.
            <br />
            Ответы с учётом вашего плана и базы знаний.
          </p>
          <Link className="assistant-link" to="/assistant">
            Открыть помощника <ArrowRight size={17} />
          </Link>
        </section>
      </div>
      {all ? (
        <section className="card task-card">
          <div className="section-top">
            <h2>
              План адаптации <span className="count">{data.total}</span>
            </h2>
            <span className="muted">Меняйте статус по мере выполнения</span>
          </div>
          {data.tasks.length ? (
            data.tasks.map((task) => (
              <TaskRow key={task.id} task={task} editable />
            ))
          ) : (
            <p className="empty">
              Задач пока нет. Наставник поможет составить план.
            </p>
          )}
        </section>
      ) : (
        <div className="details-grid">
          <section className="card task-card">
            <div className="section-top">
              <h2>
                Следующие шаги <span className="count">{next.length}</span>
              </h2>
              <Link className="text-link" to="/onboarding">
                Все задачи <ArrowRight size={15} />
              </Link>
            </div>
            <p className="section-description">
              Небольшие шаги к уверенной работе в команде
            </p>
            {next.length ? (
              next.map((task) => <TaskRow key={task.id} task={task} />)
            ) : (
              <p className="empty">
                {data.total
                  ? "Все задачи выполнены. Поздравляем!"
                  : "Задач пока нет. Обратитесь к наставнику."}
              </p>
            )}
            <Link to="/onboarding" className="task-bottom">
              Перейти к плану адаптации <ChevronRight size={17} />
            </Link>
          </section>
          <section className="card mentor-card">
            <span className="eyebrow">ПОДДЕРЖКА РЯДОМ</span>
            <h2>Ваш наставник</h2>
            {user.mentor ? (
              <>
                <span className="mentor-avatar">
                  {user.mentor.full_name
                    .split(" ")
                    .map((n) => n[0])
                    .slice(0, 2)
                    .join("")}
                </span>
                <h3>{user.mentor.full_name}</h3>
                <span className="mentor-role">
                  {roles[user.mentor.role]} · {user.mentor.team.name}
                </span>
                <p>
                  Поможет освоиться в команде
                  <br />и найти ответы на рабочие вопросы.
                </p>
              </>
            ) : (
              <p>
                Наставник ещё не назначен. Попросите команду назначить
                наставника.
              </p>
            )}
          </section>
        </div>
      )}
      <section className="card internship">
        <div className="internship-title">
          <span className="soft-icon">
            <Layers />
          </span>
          <div>
            <h2>Ваша стажировка</h2>
            <p>Всё важное о вашем старте</p>
          </div>
        </div>
        <div>
          <small>КОМАНДА</small>
          <strong>{user.team.name}</strong>
        </div>
        <div>
          <small>ДАТА НАЧАЛА</small>
          <strong>{date(user.internship_started_at)}</strong>
        </div>
        <div>
          <small>ТЕКУЩИЙ ЭТАП</small>
          <strong>
            {data.total && data.completed === data.total
              ? "Все задачи выполнены"
              : day && day > 0
                ? "Адаптация в команде"
                : "Подготовка к старту"}
          </strong>
        </div>
      </section>
      <div className="closing-note">
        Не обязательно знать всё сразу. Главное — продолжать двигаться вперёд.
      </div>
    </>
  );
}
