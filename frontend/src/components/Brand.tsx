import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
export function Brand() {
  return (
    <Link to="/" className="brand">
      <span className="brand-icon">
        <Sparkles size={23} />
      </span>
      AI-buddy<span className="beta">BETA</span>
    </Link>
  );
}
