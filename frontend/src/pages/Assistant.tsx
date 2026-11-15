import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, BookOpen, MessageSquare, Plus, Sparkles } from "lucide-react";
import { request } from "../api";
import type { ChatMessage, ChatResponse, Conversation } from "../assistant-api";
import { ActionProposals } from "../components/ActionProposals";
import { Feedback } from "../components/Feedback";
const questions = [
  "Мне нужен доступ к Jira",
  "Какие задачи у меня остались?",
  "Как получить доступ к GitLab?",
  "Как у нас проводят Code Review?",
  "Что нужно сделать в первую неделю?",
];
export function Assistant() {
  const cache = useQueryClient();
  const [active, setActive] = useState<number | null>(null);
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const conversations = useQuery({
    queryKey: ["conversations"],
    queryFn: () => request<Conversation[]>("/assistant/conversations"),
  });
  const history = useQuery({
    queryKey: ["messages", active],
    queryFn: () => request<ChatMessage[]>(`/assistant/conversations/${active}`),
    enabled: active !== null,
  });
  const send = useMutation({
    mutationFn: (message: string) =>
      request<ChatResponse>("/assistant/chat", "POST", {
        message,
        conversation_id: active,
      }),
    onSuccess: async (data) => {
      setActive(data.conversation_id);
      setText("");
      await cache.invalidateQueries({ queryKey: ["proposals"] });
      await cache.invalidateQueries({ queryKey: ["conversations"] });
      await cache.invalidateQueries({
        queryKey: ["messages", data.conversation_id],
      });
    },
  });
  const create = useMutation({
    mutationFn: () => request<Conversation>("/assistant/conversations", "POST"),
    onSuccess: async (item) => {
      setActive(item.id);
      setText("");
      send.reset();
      await cache.invalidateQueries({ queryKey: ["proposals"] });
      await cache.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [history.data, send.isPending]);
  function submit(event: FormEvent) {
    event.preventDefault();
    if (text.trim() && !send.isPending) send.mutate(text.trim());
  }
  function choose(id: number) {
    setActive(id);
    send.reset();
    setText("");
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ПОДДЕРЖКА В ВАШЕМ РИТМЕ</span>
          <h1>ИИ-помощник</h1>
          <p>
            Задачи, процессы и инструменты — с опорой на доступные вам
            источники.
          </p>
        </div>
        <span className="pill">Инструкции и помощь с доступами</span>
      </div>
      <div className="chat-layout">
        <aside className="card conversations">
          <button
            className="primary"
            disabled={send.isPending || create.isPending}
            onClick={() => create.mutate()}
          >
            <Plus size={17} /> Новый диалог
          </button>
          <span className="eyebrow">ИСТОРИЯ ДИАЛОГОВ</span>
          {conversations.isPending ? (
            <p role="status">Загружаем диалоги…</p>
          ) : conversations.error ? (
            <div role="alert">
              <p>{conversations.error.message}</p>
              <button onClick={() => void conversations.refetch()}>
                Повторить
              </button>
            </div>
          ) : conversations.data.length ? (
            conversations.data.map((item) => (
              <button
                disabled={send.isPending}
                className={
                  active === item.id ? "conversation selected" : "conversation"
                }
                key={item.id}
                onClick={() => choose(item.id)}
              >
                <MessageSquare size={16} />
                <span>{item.title}</span>
              </button>
            ))
          ) : (
            <p className="muted">Ваши диалоги появятся здесь.</p>
          )}
          {create.error && (
            <p className="error" role="alert">
              {create.error.message}
            </p>
          )}
          <div className="chat-disclaimer">
            <BookOpen size={18} />
            <p>
              Инструкции базы знаний синтетические. Создание заявки требует
              подтверждения кнопкой.
            </p>
            <Link className="text-link" to="/knowledge">
              Открыть базу знаний
            </Link>
          </div>
        </aside>
        <section className="card chat-panel" aria-label="Диалог с AI-buddy">
          <div className="chat-panel-header">
            <span className="brand-icon">
              <Sparkles size={20} />
            </span>
            <div>
              <strong>AI-buddy</strong>
              <small>Ваш персональный наставник</small>
            </div>
          </div>
          <div className="messages" aria-live="polite">
            {active !== null && history.isPending ? (
              <Feedback />
            ) : history.error ? (
              <Feedback
                error={history.error}
                retry={() => void history.refetch()}
              />
            ) : !history.data?.length ? (
              <div className="chat-welcome">
                <span className="assistant-icon">
                  <Sparkles size={28} />
                </span>
                <h2>С чего начнём?</h2>
                <p>
                  Привет! Я AI-buddy. Помогу разобраться в задачах адаптации,
                  инструментах и процессах команды. Нужен доступ к Jira?
                  Напишите об этом — я уточню детали и подготовлю заявку. Перед
                  отправкой вы проверите её и нажмёте кнопку подтверждения.
                </p>
                <div className="quick-questions">
                  {questions.map((question) => (
                    <button
                      key={question}
                      disabled={send.isPending}
                      onClick={() => {
                        setText(question);
                        send.mutate(question);
                      }}
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              history.data.map((message) => (
                <article key={message.id} className={`message ${message.role}`}>
                  <div className="message-meta">
                    <strong>
                      {message.role === "user" ? "Вы" : "AI-buddy"}
                    </strong>
                    <time dateTime={message.created_at}>
                      {new Intl.DateTimeFormat("ru-RU", {
                        hour: "2-digit",
                        minute: "2-digit",
                      }).format(new Date(message.created_at))}
                    </time>
                  </div>
                  <div className="message-content">{message.content}</div>
                  {message.sources.length > 0 && (
                    <div className="sources">
                      <span>Источники ответа</span>
                      {message.sources.map((source, index) => (
                        <Link
                          key={`${source.document_id}-${source.chunk_id}`}
                          to={`/knowledge/${source.document_id}`}
                        >
                          <BookOpen size={14} />[{index + 1}] {source.title}
                          {source.metadata?.reviewed_on
                            ? ` · Актуализация: ${source.metadata.reviewed_on}`
                            : " · Дата актуализации неизвестна"}
                        </Link>
                      ))}
                    </div>
                  )}
                </article>
              ))
            )}
            {send.isPending && (
              <div role="status" className="reply-pending">
                <span className="spinner" />
                Запрос отправлен. AI-buddy готовит ответ…
              </div>
            )}
            <ActionProposals key={active ?? "new"} conversationId={active} />
            <div ref={bottom} />
          </div>
          {send.error && (
            <p role="alert" className="error chat-error">
              {send.error.message} Текст сохранён — можно повторить отправку.
            </p>
          )}
          <form className="composer" onSubmit={submit}>
            <label className="sr-only" htmlFor="chat-message">
              Сообщение AI-buddy
            </label>
            <textarea
              id="chat-message"
              placeholder="Спросите о задачах или процессах команды…"
              maxLength={3000}
              rows={2}
              value={text}
              disabled={send.isPending}
              onChange={(event) => setText(event.target.value)}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing
                ) {
                  event.preventDefault();
                  if (text.trim() && !send.isPending) send.mutate(text.trim());
                }
              }}
            />
            <button
              className="primary"
              aria-label="Отправить сообщение"
              disabled={
                send.isPending ||
                !text.trim() ||
                history.isError ||
                (active !== null && history.isPending)
              }
            >
              <ArrowUp size={20} />
            </button>
            <small>
              Enter — отправить · Shift+Enter — новая строка · {text.length}
              /3000
            </small>
          </form>
        </section>
      </div>
    </>
  );
}
