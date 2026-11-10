import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
type Theme = "light" | "dark";
function initialTheme(): Theme {
  try {
    return localStorage.getItem("ai-buddy-theme") === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    try {
      localStorage.setItem("ai-buddy-theme", theme);
    } catch {
      /* Storage can be disabled by the browser. */
    }
  }, [theme]);
  return (
    <button
      className="icon-button theme-toggle"
      aria-label={
        theme === "light" ? "Включить тёмную тему" : "Включить светлую тему"
      }
      title={theme === "light" ? "Тёмная тема" : "Светлая тема"}
      onClick={() => setTheme(theme === "light" ? "dark" : "light")}
    >
      {theme === "light" ? <Moon size={19} /> : <Sun size={19} />}
    </button>
  );
}
