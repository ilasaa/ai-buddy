import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, Eye, EyeOff } from "lucide-react";
import { ApiError, request, type Profile } from "../api";
import { useProfile } from "../session";
import { Brand } from "../components/Brand";
import { Feedback } from "../components/Feedback";
export function Login() {
  const me = useProfile();
  const cache = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const login = useMutation({
    mutationFn: () =>
      request<Profile>("/auth/login", "POST", { email, password }),
    onSuccess: (user) => {
      cache.removeQueries({ queryKey: ["onboarding"] });
      cache.setQueryData(["me"], user);
    },
  });
  if (me.isPending) return <Feedback />;
  if (me.data) return <Navigate to="/" replace />;
  if (me.error && (!(me.error instanceof ApiError) || me.error.status !== 401))
    return <Feedback error={me.error} retry={() => void me.refetch()} />;
  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate();
  }
  return (
    <main className="login">
      <section className="login-story">
        <Brand />
        <div>
          <span className="eyebrow">НОВАЯ КОМАНДА. УВЕРЕННЫЙ СТАРТ.</span>
          <h1>
            Большой путь
            <br />
            начинается
            <br />с первого шага<span>.</span>
          </h1>
          <p>
            Знакомьтесь с командой, двигайтесь по плану
            <br />и отмечайте свои первые победы.
          </p>
          <div className="story-steps">
            <span>
              <Check /> Понятный план
            </span>
            <span>
              <Check /> Поддержка рядом
            </span>
          </div>
        </div>
        <small>Демонстрационный прототип · Hack&Change 2026</small>
      </section>
      <section className="login-form">
        <form onSubmit={submit}>
          <span className="pill">ВАШ ЛИЧНЫЙ КАБИНЕТ</span>
          <h2>Рады знакомству 👋</h2>
          <p>Войдите, чтобы продолжить свой путь в команде.</p>
          <label htmlFor="email">Рабочий email</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.ru"
          />
          <label htmlFor="password">Пароль</label>
          <div className="password">
            <input
              id="password"
              type={show ? "text" : "password"}
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="button"
              className="icon-button"
              aria-label={show ? "Скрыть пароль" : "Показать пароль"}
              onClick={() => setShow(!show)}
            >
              {show ? <EyeOff size={19} /> : <Eye size={19} />}
            </button>
          </div>
          {login.error && (
            <p role="alert" className="error">
              {login.error.message}
            </p>
          )}
          <button className="primary login-submit" disabled={login.isPending}>
            {login.isPending ? "Входим…" : "Войти"}
            <ArrowRight size={18} />
          </button>
          <small>
            Нет доступа? Обратитесь к вашему наставнику.
            <br />
            Публичная регистрация пока недоступна.
          </small>
        </form>
      </section>
    </main>
  );
}
