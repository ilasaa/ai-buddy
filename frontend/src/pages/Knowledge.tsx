import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, ChevronLeft } from "lucide-react";
import { request } from "../api";
import type { Document } from "../assistant-api";
import { Feedback } from "../components/Feedback";
export function Knowledge() {
  const { documentId } = useParams();
  const query = useQuery({
    queryKey: ["knowledge", documentId ?? "list"],
    queryFn: () =>
      documentId
        ? request<Document>(`/knowledge/${documentId}`).then((item) => [item])
        : request<Document[]>("/knowledge"),
  });
  if (query.isPending) return <Feedback />;
  if (query.error)
    return <Feedback error={query.error} retry={() => void query.refetch()} />;
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ДОСТУПНЫЕ ИСТОЧНИКИ</span>
          <h1>База знаний</h1>
          <p>
            Синтетические инструкции прототипа. Не внутренние регламенты Авито.
          </p>
        </div>
      </div>
      {documentId && (
        <Link className="text-link" to="/knowledge">
          <ChevronLeft size={16} /> Все документы
        </Link>
      )}
      {query.data.length ? (
        query.data.map((document) => (
          <article className="card knowledge-document" key={document.id}>
            <span className="pill">
              {document.is_public ? "Общий документ" : "Документ вашей команды"}
            </span>
            <h2>
              {documentId ? (
                document.title
              ) : (
                <Link to={`/knowledge/${document.id}`}>
                  <BookOpen size={18} /> {document.title}
                </Link>
              )}
            </h2>
            <small>Источник: {document.source}</small>
            {documentId && (
              <div className="document-content">{document.content}</div>
            )}
          </article>
        ))
      ) : (
        <section className="card">
          <p>Документы ещё не проиндексированы. Обратитесь к администратору.</p>
        </section>
      )}
    </>
  );
}
