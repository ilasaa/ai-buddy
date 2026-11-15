export interface AccessRequest {
  task_id?: number | null;
  id: number;
  user_id: number;
  resource: string;
  project_key: string;
  permission: string;
  justification: string;
  status: string;
  approver_id: number | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  routing: string;
  events?: {
    id: number;
    event_type: string;
    comment: string;
    created_at: string;
  }[];
}
export interface Proposal {
  id: string;
  state: string;
  expires_at: string;
  conversation_id: number | null;
  parameters: {
    task_id?: number | null;
    resource: string;
    project_key: string;
    permission: string;
    justification: string;
  };
}
export const statuses: Record<string, string> = {
  pending: "Ожидает согласования",
  approved: "Согласована — доступ ещё не выдан",
  rejected: "Отклонена",
};
export const permission = (value: string) =>
  value === "write" ? "Редактирование" : "Просмотр";
