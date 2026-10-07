"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, Meta, RequestType, Role, ROLE_LABEL, TYPE_LABEL } from "@/lib/api";

const PLACEHOLDER: Record<Role, string> = {
  pm: "例如：客戶希望在 Exclusion Area 之外，也能依時段過濾事件……（可直接貼上客戶 email 或會議記錄）",
  fae: "例如：客戶現場 staging2 的 Ensemble Gate 一直判定失敗，log 如附件……",
  rd: "貼上「我目前的理解」和「想問 PM 的問題」。例如：\n我的理解：標注存在 middleware 自己的 processed_event_annotations……\n想請教：1. 需求來源？2. 標完要給誰用？",
};

// RD mostly clarifies existing work; PM and FAE usually bring a feature
const DEFAULT_TYPE: Record<Role, RequestType> = { pm: "feature", fae: "feature", rd: "task" };

export default function NewRequest() {
  const router = useRouter();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [role, setRole] = useState<Role>("pm");
  const [type, setType] = useState<RequestType>("feature");
  const [template, setTemplate] = useState<string>("");
  const [budget, setBudget] = useState<string>("");
  const [audience, setAudience] = useState<Role>("rd");
  const [assignee, setAssignee] = useState("");
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.meta().then((m) => {
      setMeta(m);
      setBudget(m.default_question_budget);
    });
    api.me().then((me) => {
      pickRole(me.default_role);
    });
  }, []);

  function pickRole(r: Role) {
    setRole(r);
    setType(DEFAULT_TYPE[r]);
  }

  const defaultTemplate = meta?.default_template[`${role}:${type}`] ?? "";
  const defaultAudience = meta?.default_audience[role] ?? (role === "rd" ? "pm" : "rd");
  useEffect(() => setAudience(defaultAudience), [defaultAudience]);
  useEffect(() => setTemplate(defaultTemplate), [defaultTemplate]);

  async function submit() {
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.set("role", role);
    form.set("request_type", type);
    form.set("text", text);
    if (template) form.set("template", template);
    if (budget) form.set("question_budget", budget);
    form.set("audience", audience);
    form.set("assignee", assignee.trim());
    files.forEach((f) => form.append("files", f));
    try {
      const { id } = await api.createInterview(form);
      if (role !== "pm") api.setDefaultRole(role).catch(() => {});
      router.push(`/interviews/${id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <h1>新增 Request</h1>
      <div className="card stack">
        <div className="row">
          <span className="muted small" style={{ width: 70 }}>Role</span>
          <div className="seg">
            {(meta?.roles ?? ["pm", "fae", "rd"]).map((r) => (
              <button key={r} className={role === r ? "on" : ""} onClick={() => pickRole(r as Role)}>
                {ROLE_LABEL[r as Role]}
              </button>
            ))}
          </div>
        </div>
        <div className="row">
          <span className="muted small" style={{ width: 70 }}>類型</span>
          <div className="seg">
            {(meta?.request_types ?? ["feature", "bug", "task"]).map((t) => (
              <button key={t} className={type === t ? "on" : ""} onClick={() => setType(t as RequestType)}>
                {TYPE_LABEL[t as RequestType]}
              </button>
            ))}
          </div>
        </div>
        <div className="row">
          <span className="muted small" style={{ width: 70 }}>To</span>
          <div className="seg">
            {(meta?.roles ?? ["pm", "fae", "rd"]).map((r) => (
              <button key={r} className={audience === r ? "on" : ""} onClick={() => setAudience(r as Role)}>
                {ROLE_LABEL[r as Role]}
                {r === defaultAudience ? "（預設）" : ""}
              </button>
            ))}
          </div>
          <input
            type="email"
            aria-label="指派給"
            placeholder="指派給（選填），例如 kevin@linkervision.com"
            value={assignee}
            onChange={(e) => setAssignee(e.target.value)}
            style={{ flex: 1, minWidth: 220, width: "auto" }}
          />
        </div>
        <p className="muted small" style={{ margin: "-6px 0 0 78px" }}>
          小精靈會照 {ROLE_LABEL[audience]} 需要知道的事來問、來寫 Spec；填了指派對象，開 ADO 票時會設成 Assigned To。
        </p>
        <div className="row">
          <span className="muted small" style={{ width: 70 }}>拷問方式</span>
          <select value={template} onChange={(e) => setTemplate(e.target.value)} style={{ width: "auto" }}>
            {meta?.templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
                {t.id === defaultTemplate ? "（預設）" : ""}
              </option>
            ))}
          </select>
        </div>
        <div className="row">
          <span className="muted small" style={{ width: 70 }}>要問多細</span>
          <div className="seg">
            {meta?.question_budgets.map((b) => (
              <button key={b.id} className={budget === b.id ? "on" : ""} onClick={() => setBudget(b.id)}>
                {b.label}（{b.limit === 0 ? "直接寫 Spec" : b.limit ? `最多 ${b.limit} 題` : "不限題數"}）
              </button>
            ))}
          </div>
          <span className="muted small">
            {budget === "none"
              ? "不出題：小精靈查完資料直接寫 Spec，自己做的決定都會列成 Assumption，請檢查後再開票。適合已經很清楚的小需求。"
              : budget === "thorough"
                ? "問到每個分支都清楚為止。"
                : "只問最關鍵的決定；沒問到的，小精靈會在 Spec 裡寫成 Assumption 或 Open Question。"}
          </span>
        </div>
        <label className="field">
          <span>需求內容</span>
          <textarea
            rows={10}
            placeholder={PLACEHOLDER[role]}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </label>
        <label className="field">
          <span>附件（圖片、PDF、文字檔、log；單檔 20MB 內）— 會一起附到 ADO 票上</span>
          <input
            type="file"
            multiple
            accept="image/*,.pdf,.txt,.log,.md,.csv,.json,.yaml,.yml"
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          />
        </label>
        {role === "rd" && (
          <div className="notice info small">
            RD 釐清流程：AI 會把內容拆成 <b>Premise</b>（請對方確認的理解）和問題，先對照程式碼驗證 Premise，
            你檢查修改後再轉交給 PM 回答。
          </div>
        )}
        {error && <div className="notice danger">{error}</div>}
        <div className="row">
          <span className="spacer" />
          <button className="primary" disabled={busy || (!text.trim() && files.length === 0)} onClick={submit}>
            {busy ? "建立中…" : budget === "none" ? "產出 Spec" : "開始拷問"}
          </button>
        </div>
      </div>
    </div>
  );
}
