import { CircleHelp } from "lucide-react";
export function Feedback({
  error,
  retry,
}: {
  error?: Error | null;
  retry?: () => void;
}) {
  return (
    <div className="feedback" role={error ? "alert" : "status"}>
      {error ? (
        <>
          <CircleHelp />
          <p>{error.message}</p>
          {retry && <button onClick={retry}>Попробовать снова</button>}
        </>
      ) : (
        <>
          <span className="spinner" />
          <p>Загружаем ваш кабинет…</p>
        </>
      )}
    </div>
  );
}
