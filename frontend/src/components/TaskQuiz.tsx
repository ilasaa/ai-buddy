import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { request } from "../api";
import { Feedback } from "./Feedback";
type Attempt = {
  id: number;
  score: number;
  passed: boolean;
  feedback: { correct: boolean; explanation: string }[];
};
type Quiz = {
  title: string;
  passing_score: number;
  questions: { text: string; options: string[] }[];
  attempts: Attempt[];
};
export function TaskQuiz({
  taskId,
  completed = false,
}: {
  taskId: number;
  completed?: boolean;
}) {
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const cache = useQueryClient();
  const query = useQuery({
    queryKey: ["quiz", taskId],
    queryFn: () => request<Quiz>(`/quizzes/tasks/${taskId}`),
  });
  const submit = useMutation({
    mutationFn: () =>
      request<Attempt>(`/quizzes/tasks/${taskId}`, "POST", {
        answers: query.data!.questions.map((_, i) => answers[i] ?? -1),
      }),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["quiz", taskId] });
      await cache.invalidateQueries({ queryKey: ["adaptation"] });
      await cache.invalidateQueries({ queryKey: ["onboarding"] });
    },
  });
  if (query.isPending) return <Feedback />;
  if (query.error) return <Feedback error={query.error} />;
  const q = query.data;
  return (
    <section>
      <h3>{q.title}</h3>
      <p>
        Проходной результат: {q.passing_score} из {q.questions.length}
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit.mutate();
        }}
      >
        {q.questions.map((question, i) => (
          <fieldset key={i} disabled={completed}>
            <legend>{question.text}</legend>
            {question.options.map((option, j) => (
              <label key={j}>
                <input
                  type="radio"
                  name={`quiz-${taskId}-${i}`}
                  checked={answers[i] === j}
                  onChange={() => setAnswers({ ...answers, [i]: j })}
                  required
                />
                {option}
              </label>
            ))}
          </fieldset>
        ))}
        <button disabled={completed || submit.isPending}>
          Проверить ответы
        </button>
      </form>
      {submit.error && <p role="alert">{submit.error.message}</p>}
      {q.attempts.map((a) => (
        <article key={a.id}>
          <p>
            Попытка №{a.id}: {a.score} —{" "}
            {a.passed ? "Зачтено" : "Попробуйте ещё раз"}
          </p>
          {a.feedback.map((f, i) => (
            <p key={i}>
              Вопрос {i + 1}: {f.explanation}
            </p>
          ))}
        </article>
      ))}
    </section>
  );
}
