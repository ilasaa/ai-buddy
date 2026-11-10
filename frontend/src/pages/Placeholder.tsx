import { Link } from "react-router-dom";
import { ArrowRight, Sparkles } from "lucide-react";
export function Placeholder({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <section className="card placeholder">
      <span className="placeholder-icon">
        <Sparkles size={34} />
      </span>
      <span className="pill">В РАЗРАБОТКЕ</span>
      <h1>{title}</h1>
      <p>{description}</p>
      <Link className="primary" to="/">
        Вернуться на главную <ArrowRight size={18} />
      </Link>
    </section>
  );
}
