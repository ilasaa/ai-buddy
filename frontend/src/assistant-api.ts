export interface Source {
  document_id: number;
  chunk_id: number;
  title: string;
  source: string;
  score: number;
  metadata?: { reviewed_on?: string; scope?: string };
}
export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  sources: Source[];
}
export interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
}
export interface ChatResponse {
  conversation_id: number;
  message: ChatMessage;
  prompt_tokens: number;
  completion_tokens: number;
  rag_used: boolean;
}
export interface Document {
  id: number;
  title: string;
  source: string;
  is_public: boolean;
  content: string;
}
