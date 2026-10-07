export type Role = "pm" | "fae" | "rd";
export type RequestType = "feature" | "bug" | "task";

export interface AdoStatus {
  connected: boolean;
  dev_fallback: boolean;
  display_name: string | null;
  expires_on: string | null;
  expiring_soon: boolean;
  expired: boolean;
  token_page: string;
}

export interface Me {
  email: string;
  display_name: string | null;
  default_role: Role;
  ado: AdoStatus;
}

export interface Meta {
  roles: Role[];
  request_types: RequestType[];
  templates: { id: string; label: string }[];
  default_template: Record<string, string>;
  question_budgets: { id: string; label: string; limit: number | null }[];
  default_question_budget: string;
  default_audience: Record<Role, Role>;
  default_parent_id: number;
  severities: string[];
  auth_mode: "observ" | "dev";
  single_user: boolean;
  teams_enabled: boolean;
}

export interface InterviewSummary {
  id: string;
  requester: string;
  role: Role;
  request_type: RequestType;
  status: "interviewing" | "spec_draft" | "ticketed" | "decision_record";
  title: string;
  ticket_id: number | null;
  ticket_url: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface Question {
  id: string;
  ref: string;
  round: number;
  kind: "question" | "premise";
  title: string;
  body: string;
  options: string[];
  recommendation: string | null;
  rationale: string | null;
  ai_note: string | null;
  core: boolean;
  respondent: string;
  handoff_id: string | null;
  status: "pending" | "answered" | "unknown" | "skipped" | "confirmed" | "corrected" | "withdrawn";
  answer_text: string | null;
  answered_by: string | null;
  answered_at: string | null;
  can_respond: boolean;
  can_skip: boolean;
}

export interface HandoffInfo {
  id: string;
  to: string;
  status: "open" | "completed" | "recalled";
  reminders_sent: number;
  created_at: string;
  pending: number;
}

export interface NewTerm {
  term: string;
  meaning: string;
  conflict: string | null;
}

export interface EngineProgress {
  started_at: string;
  reads: string[];
  read_count: number;
  searches: number;
}

export interface InterviewDetail extends InterviewSummary {
  product: string;
  template: string;
  template_label: string;
  request_text: string;
  round: number;
  question_budget: number | null;
  questions_asked: number;
  audience: Role;
  assignee: string | null;
  engine_busy: boolean;
  engine_done: boolean;
  engine_error: string | null;
  engine_progress: EngineProgress | null;
  summary: string | null;
  new_terms: NewTerm[];
  spec_markdown: string | null;
  suggested_priority: number | null;
  suggested_severity: string | null;
  parent_id: number | null;
  default_parent_id: number;
  is_requester: boolean;
  unknown_core_count: number;
  unknown_warning: boolean;
  questions: Question[];
  attachments: { id: string; filename: string; content_type: string; size: number }[];
  handoffs: HandoffInfo[];
}

export interface WorkItem {
  id: number;
  title: string;
  work_item_type: string;
  state: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (init.body && !(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const res = await fetch(`/api${path}`, { ...init, headers: { ...headers, ...(init.headers as object) } });
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/")) {
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
  }
  if (!res.ok) {
    let msg = res.status >= 500 ? `伺服器錯誤（${res.status}）` : res.statusText;
    try {
      const data = await res.json();
      msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  login: (email: string, password: string) =>
    request<{ email: string }>("/auth/login", { method: "POST", body: json({ email, password }) }),
  logout: () => request("/auth/logout", { method: "POST" }),
  me: () => request<Me>("/me"),
  setDefaultRole: (default_role: Role) => request("/me", { method: "PUT", body: json({ default_role }) }),
  connectAdo: (pat: string, expires_on: string | null) =>
    request<AdoStatus>("/me/ado", { method: "PUT", body: json({ pat, expires_on }) }),
  disconnectAdo: () => request<AdoStatus>("/me/ado", { method: "DELETE" }),
  meta: () => request<Meta>("/meta"),
  searchWorkItems: (q: string) => request<WorkItem[]>(`/ado/work-items?q=${encodeURIComponent(q)}`),

  listInterviews: (scope: "all" | "mine" | "for-me") => request<InterviewSummary[]>(`/interviews?scope=${scope}`),
  createInterview: (form: FormData) => request<{ id: string }>("/interviews", { method: "POST", body: form }),
  interview: (id: string) => request<InterviewDetail>(`/interviews/${id}`),
  addAttachments: (id: string, form: FormData) =>
    request(`/interviews/${id}/attachments`, { method: "POST", body: form }),
  respond: (qid: string, action: string, text?: string) =>
    request(`/questions/${qid}/respond`, { method: "POST", body: json({ action, text }) }),
  editQuestion: (qid: string, patch: { title?: string; body?: string; options?: string[] }) =>
    request(`/questions/${qid}`, { method: "PATCH", body: json(patch) }),
  withdraw: (qid: string) => request(`/questions/${qid}/withdraw`, { method: "POST" }),
  retry: (id: string) => request(`/interviews/${id}/retry`, { method: "POST" }),
  deleteInterview: (id: string) => request(`/interviews/${id}`, { method: "DELETE" }),
  handoff: (id: string, question_ids: string[], to_email: string, notify: boolean) =>
    request<{ id: string; link: string }>(`/interviews/${id}/handoffs`, {
      method: "POST",
      body: json({ question_ids, to_email, notify }),
    }),
  recall: (hid: string) => request(`/handoffs/${hid}/recall`, { method: "POST" }),
  finish: (id: string) => request(`/interviews/${id}/finish`, { method: "POST" }),
  saveSpec: (id: string, title: string, markdown: string) =>
    request(`/interviews/${id}/spec`, { method: "PUT", body: json({ title, markdown }) }),
  createTicket: (
    id: string,
    body: {
      title: string;
      parent_id: number | null;
      priority: number | null;
      severity: string | null;
      notify: boolean;
      assignee: string | null;
    },
  ) => request<{ ticket_id: number; ticket_url: string }>(`/interviews/${id}/ticket`, { method: "POST", body: json(body) }),
  decisionRecord: (id: string, title: string) =>
    request<{ link: string }>(`/interviews/${id}/decision-record`, { method: "POST", body: json({ title }) }),
};

export const ROLE_LABEL: Record<Role, string> = { pm: "PM", fae: "FAE", rd: "RD" };
export const TYPE_LABEL: Record<RequestType, string> = { feature: "Feature", bug: "Bug", task: "Task" };
export const STATUS_LABEL: Record<InterviewSummary["status"], string> = {
  interviewing: "拷問中",
  spec_draft: "Spec 草稿",
  ticketed: "已開票",
  decision_record: "Decision Record",
};
export const WORK_ITEM_TYPE: Record<RequestType, string> = { feature: "User Story", bug: "Bug", task: "Task" };

/** Confirm text for deleting an Interview; an opened ADO Ticket is not touched. */
export function deleteConfirmText(i: Pick<InterviewSummary, "title" | "ticket_id">): string {
  return (
    `確定要刪除「${i.title}」？\n\n題目、回答、轉交和附件都會一起刪除，無法復原。` +
    (i.ticket_id ? `\nAzure DevOps 上的 #${i.ticket_id} 不會被刪除。` : "")
  );
}
