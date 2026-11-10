import type { Onboarding } from "../api";
export function Progress({ data }: { data: Onboarding }) {
  return (
    <section className="card progress-card">
      <div className="section-top">
        <span className="eyebrow">ВАШ ПРОГРЕСС</span>
        <span className="pill">Адаптация</span>
      </div>
      <div className="progress-number">
        {data.percent}
        <span>%</span>
        <span className="progress-caption">
          Постепенно становитесь
          <br />
          частью команды
        </span>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label="Прогресс адаптации"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={data.percent}
      >
        <div style={{ width: `${data.percent}%` }} />
      </div>
      <div className="progress-bottom">
        <span>
          <strong>{data.completed}</strong> из {data.total} задач выполнено
        </span>
        <span>
          {data.total > 0 && data.completed === data.total
            ? "Отличная работа!"
            : "Так держать!"}
        </span>
      </div>
    </section>
  );
}
