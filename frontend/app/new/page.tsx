"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Hint from "@/components/Hint";
import PersonInput from "@/components/PersonInput";
import { api, Meta, RequestType, Role, ROLE_LABEL, TYPE_LABEL } from "@/lib/api";

const PLACEHOLDER: Record<Role, string> = {
  pm: "例如：客戶希望在 Exclusion Area 之外，也能依時段過濾事件……（可直接貼上客戶 email 或會議記錄）",
  fae: "例如：客戶現場 staging2 的 Ensemble Gate 一直判定失敗，log 如附件……",
  rd: "貼上「我目前的理解」和「想問 PM 的問題」。例如：\n我的理解：標注存在 middleware 自己的 processed_event_annotations……\n想請教：1. 需求來源？2. 標完要給誰用？",
};

interface Example {
  title: string;
  topic: string;
  hint: string;
  role: Role;
  type: RequestType;
  audience: Role;
  template: string;
  budget: string;
  text: string;
}

// Real requests from the trial, one per typical path through the form
const EXAMPLES: Example[] = [
  {
    title: "FAE 回報 bug",
    topic: "v19 改了白名單 event id，歷史事件查不到",
    hint: "原因和影響都清楚 → 不問，直接寫 Spec",
    role: "fae",
    type: "bug",
    audience: "rd",
    template: "quick_bug_technical",
    budget: "none",
    text:
      "上次給 v19 時改動了白名單的 event id，被改掉的 event id 在歷史事件查不到。\n" +
      "影響：客戶查詢改版前的事件時，用新的 event id 找不到資料。",
  },
  {
    title: "RD 想問 PM",
    topic: "歷史頁面打 tag 的用途，會不會和 Observ tag 重複",
    hint: "先寫自己的理解和疑問 → 釐清後轉交 PM",
    role: "rd",
    type: "task",
    audience: "pm",
    template: "clarify",
    budget: "standard",
    text:
      "middleware 歷史頁面打 tag，想先釐清：\n" +
      "1. 打 tag 的用途是什麼？\n" +
      "2. 是否需要標示「需要二次驗證的模型」？像 CR3 好像也會請 Oleksi 重新訓練，不確定這樣標註對他們有沒有幫助。\n" +
      "3. 未來統計準確度時，是看 Observ 的 tag，還是看 middleware 的答案？\n" +
      "我覺得兩套標註的目的不要重複比較好。",
  },
  {
    title: "PM 提新功能",
    topic: "準確度頁面可以匯出報表",
    hint: "一句話的需求 → 標準拷問補齊細節",
    role: "pm",
    type: "feature",
    audience: "rd",
    template: "grill_product",
    budget: "standard",
    text: "在 middleware web 的準確度頁面，可以匯出檔案（報表）。",
  },
];

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

  function applyExample(e: Example) {
    if (text.trim() && text !== e.text && !confirm("要用範例取代目前填的需求內容嗎？")) return;
    setRole(e.role);
    setType(e.type);
    setAudience(e.audience);
    setTemplate(e.template);
    setBudget(e.budget);
    setText(e.text);
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
      <h1>新增需求</h1>
      <section className="stack" style={{ gap: 8 }} aria-label="範例">
        <span className="muted small">不知道怎麼填？點一個範例，會幫你把表單填好，再改成自己的內容：</span>
        <div className="examples">
          {EXAMPLES.map((e) => (
            <button key={e.title} className="example" onClick={() => applyExample(e)}>
              <b>{e.title}</b>
              <span className="topic">「{e.topic}」</span>
              <span>{e.hint}</span>
            </button>
          ))}
        </div>
      </section>
      <div className="card stack">
        <div className="row">
          <span className="form-label">
            Role
            <Hint label="Role">
              你這次的身份。決定預設的拷問方式，以及小精靈能看的資料：PM、FAE 只看文件和 spec；RD 可以看程式碼。不影響權限。
            </Hint>
          </span>
          <div className="seg">
            {(meta?.roles ?? ["pm", "fae", "rd"]).map((r) => (
              <button key={r} className={role === r ? "on" : ""} onClick={() => pickRole(r as Role)}>
                {ROLE_LABEL[r as Role]}
              </button>
            ))}
          </div>
        </div>
        <div className="row">
          <span className="form-label">
            類型
            <Hint label="類型">Feature 是新功能，Bug 是問題回報，Task 是釐清或小工作。會決定預設的拷問方式和開出的票種。</Hint>
          </span>
          <div className="seg">
            {(meta?.request_types ?? ["feature", "bug", "task"]).map((t) => (
              <button key={t} className={type === t ? "on" : ""} onClick={() => setType(t as RequestType)}>
                {TYPE_LABEL[t as RequestType]}
              </button>
            ))}
          </div>
        </div>
        <details className="advanced">
          <summary>
            進階設定
            <span className="muted small">
              To {ROLE_LABEL[audience]}
              {assignee.trim() ? `（指派 ${assignee.trim().split("@")[0]}）` : ""} ·{" "}
              {meta?.templates.find((t) => t.id === template)?.label ?? template} ·{" "}
              {meta?.question_budgets.find((b) => b.id === budget)?.label ?? budget}
            </span>
          </summary>
          <div className="stack">
            <div className="row">
              <span className="form-label">
                To
                <Hint label="To">
                  Spec 寫給誰看。小精靈會照對方需要知道的事來問、來寫。PM、FAE 預設給 RD；RD 預設給 PM。
                </Hint>
              </span>
              <div className="seg">
                {(meta?.roles ?? ["pm", "fae", "rd"]).map((r) => (
                  <button key={r} className={audience === r ? "on" : ""} onClick={() => setAudience(r as Role)}>
                    {ROLE_LABEL[r as Role]}
                    {r === defaultAudience ? "（預設）" : ""}
                  </button>
                ))}
              </div>
              <PersonInput
                label="指派給"
                placeholder="指派給（選填），輸入名字或 email 搜尋"
                value={assignee}
                onChange={setAssignee}
                style={{ flex: 1, minWidth: 220, width: "auto" }}
              />
            </div>
            <p className="muted small" style={{ margin: "-6px 0 0 96px" }}>
              小精靈會照 {ROLE_LABEL[audience]} 需要知道的事來問、來寫 Spec；填了指派對象，開 ADO 票時會設成 Assigned To。
            </p>
            <div className="row">
              <span className="form-label">
                拷問方式
                <Hint label="拷問方式">
                  grill-with-docs：一輪輪問到清楚；快速 bug 回報：只問重現步驟和影響；釐清：把你的理解拆成 Premise 請對方確認。
                </Hint>
              </span>
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
              <span className="form-label">
                要問多細
                <Hint label="要問多細">
                  最多問幾題。選「不問」會直接寫 Spec；題數到了就結束，沒問到的寫成 Assumption。過程中隨時可以按「夠了，產出 Spec」。
                </Hint>
              </span>
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
          </div>
        </details>
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
