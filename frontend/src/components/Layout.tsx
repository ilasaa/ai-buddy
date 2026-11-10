import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  ChevronRight,
  ClipboardList,
  Home,
  LogOut,
  Menu,
  Sparkles,
  Ticket,
  X,
} from "lucide-react";
import { request, type Profile } from "../api";
import { roles } from "../labels";
import { ThemeToggle } from "./ThemeToggle";
import { Brand } from "./Brand";
const navigation = [
  { to: "/", label: "Главная", icon: Home },
  { to: "/onboarding", label: "Моя адаптация", icon: ClipboardList },
  { to: "/assistant", label: "ИИ-помощник", icon: Sparkles },
  { to: "/requests", label: "Мои заявки", icon: Ticket },
  { to: "/knowledge", label: "База знаний", icon: BookOpen },
];
export function Layout({ user }: { user: Profile }) {
  const cache = useQueryClient();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const logout = useMutation({
    mutationFn: () => request<void>("/auth/logout", "POST"),
    onSuccess: async () => {
      await cache.cancelQueries();
      cache.removeQueries({ predicate: (query) => query.queryKey[0] !== "me" });
      cache.setQueryData(["me"], null);
    },
  });
  return (
    <div className="shell">
      <aside className={open ? "sidebar opened" : "sidebar"}>
        <div className="sidebar-brand">
          <Brand />
          <button
            className="mobile icon-button"
            aria-label="Закрыть меню"
            onClick={() => setOpen(false)}
          >
            <X />
          </button>
        </div>
        <div className="workspace">
          <span className="workspace-icon">{user.team.name[0]}</span>
          <div>
            <strong>Рабочее пространство</strong>
            <small>{user.team.name}</small>
          </div>
        </div>
        <span className="nav-label">МОЁ ПРОСТРАНСТВО</span>
        <nav>
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              onClick={() => setOpen(false)}
            >
              <item.icon size={20} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="mini-symbol">
            <Sparkles />
          </div>
          <strong>Осваивайтесь в своём темпе</strong>
          <p>
            Каждый маленький шаг —<br />
            часть большого пути.
          </p>
          <Link to="/onboarding">
            К плану адаптации <ArrowRight size={15} />
          </Link>
        </div>
        <small className="demo-note">Синтетические данные · Demo</small>
      </aside>
      <div className="main-column">
        <header>
          <div className="breadcrumbs">
            <button
              className="mobile icon-button"
              aria-label="Открыть меню"
              onClick={() => setOpen(true)}
            >
              <Menu />
            </button>
            <span>Моё пространство</span>
            <ChevronRight size={15} />
            <strong>
              {navigation.find((n) => n.to === location.pathname)?.label ??
                "Страница"}
            </strong>
          </div>
          <div className="user-menu">
            <ThemeToggle />
            <span className="avatar">
              {user.full_name
                .split(" ")
                .map((n) => n[0])
                .slice(0, 2)
                .join("")}
            </span>
            <div>
              <strong>{user.full_name}</strong>
              <small>{roles[user.role]}</small>
            </div>
            <button
              className="icon-button"
              title="Выйти"
              aria-label="Выйти из аккаунта"
              disabled={logout.isPending}
              onClick={() => logout.mutate()}
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>
        {logout.error && (
          <p className="error" role="alert">
            {logout.error.message}
          </p>
        )}
        <main className="content">
          <Outlet context={user} />
        </main>
        <footer>
          <span>AI-buddy · Поддержка на каждом шаге</span>
          <span>Локальный прототип · 2026</span>
        </footer>
      </div>
    </div>
  );
}
