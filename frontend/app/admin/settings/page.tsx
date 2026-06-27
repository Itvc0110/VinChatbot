"use client";

import { useState } from "react";
import { Toast } from "@/components/ui/primitives";
import { IconCheck } from "@/components/shell/icons";
import { usePortal } from "@/lib/portalI18n";

// Admin System Settings (Phase 4, new route). Demo-only: there is no settings backend, so all controls
// are local demo state. No live API / auth / RBAC logic is wired — this is a presentational scaffold.

interface User { name: string; role: string; department: string; active: boolean }
type Module = "tickets" | "kb" | "context" | "settings";
const MODULE_KEYS: Module[] = ["tickets", "kb", "context", "settings"];
const ROLES = ["System Admin", "Registrar Staff", "Finance Staff", "Read-only"];

const SEED_USERS: User[] = [
  { name: "Dr. Sarah Jenkins", role: "System Admin", department: "IT Services", active: true },
  { name: "Mai Tran", role: "Registrar Staff", department: "Office of the Registrar", active: true },
  { name: "John Pham", role: "Finance Staff", department: "Bursar / Finance", active: true },
  { name: "Linh Do", role: "Read-only", department: "Student Affairs", active: false },
];
const SEED_PERMS: Record<string, Record<Module, boolean>> = {
  "System Admin": { tickets: true, kb: true, context: true, settings: true },
  "Registrar Staff": { tickets: true, kb: true, context: false, settings: false },
  "Finance Staff": { tickets: true, kb: false, context: false, settings: false },
  "Read-only": { tickets: false, kb: false, context: false, settings: false },
};
const SEED_ROUTING = [
  { category: "Tuition & fees", department: "Bursar / Finance" },
  { category: "Transcript requests", department: "Office of the Registrar" },
  { category: "Course registration", department: "Office of the Registrar" },
  { category: "IT / login issues", department: "IT Services" },
];

interface SettingsStrings {
  intro: string;
  adminUsers: string;
  addUser: string;
  name: string;
  role: string;
  department: string;
  status: string;
  active: string;
  disabled: string;
  rbac: string;
  allowed: string;
  denied: string;
  routingRules: string;
  addRule: string;
  questionCategory: string;
  routesToDepartment: string;
  notificationPreferences: string;
  dailyDigest: string;
  dailyDigestSub: string;
  urgentAlerts: string;
  urgentAlertsSub: string;
  ticketReplies: string;
  ticketRepliesSub: string;
  weeklyAnalytics: string;
  weeklyAnalyticsSub: string;
  dataSourceSettings: string;
  recrawlFrequency: string;
  optDaily: string;
  optWeekly: string;
  optMonthly: string;
  optManual: string;
  chatLogRetention: string;
  redactPii: string;
  maskIdentifiers: string;
  redactPiiLabel: string;
  generalAccess: string;
  systemLanguage: string;
  maintenanceMode: string;
  disablePortal: string;
  saveChanges: string;
  modules: Record<Module, string>;
  toastAddUser: string;
  toastAddRule: string;
  toastPii: string;
  toastSaved: string;
}

const STR: Record<"en" | "vi", SettingsStrings> = {
  en: {
    intro: "Configure roles, permissions, routing, and system behavior. Changes here are demo-only.",
    adminUsers: "Admin Users",
    addUser: "+ Add User",
    name: "Name",
    role: "Role",
    department: "Department",
    status: "Status",
    active: "Active",
    disabled: "Disabled",
    rbac: "Roles & Permissions (RBAC)",
    allowed: "allowed",
    denied: "denied",
    routingRules: "Routing Rules",
    addRule: "+ Add Rule",
    questionCategory: "Question category",
    routesToDepartment: "Routes to department",
    notificationPreferences: "Notification Preferences",
    dailyDigest: "Daily digest",
    dailyDigestSub: "Summary of new unresolved questions",
    urgentAlerts: "Urgent alerts",
    urgentAlertsSub: "High-priority tickets & indexing failures",
    ticketReplies: "Ticket replies",
    ticketRepliesSub: "When a student responds",
    weeklyAnalytics: "Weekly analytics",
    weeklyAnalyticsSub: "Vinnie quality report",
    dataSourceSettings: "Data & Source Settings",
    recrawlFrequency: "Re-crawl frequency",
    optDaily: "Daily",
    optWeekly: "Weekly",
    optMonthly: "Monthly",
    optManual: "Manual only",
    chatLogRetention: "Chat log retention (days)",
    redactPii: "Redact PII in logs",
    maskIdentifiers: "Mask student identifiers",
    redactPiiLabel: "Redact PII",
    generalAccess: "General & Access Control",
    systemLanguage: "System language",
    maintenanceMode: "Maintenance mode",
    disablePortal: "Disable student portal access",
    saveChanges: "Save changes",
    modules: { tickets: "Tickets", kb: "Knowledge Base", context: "Context", settings: "Settings" },
    toastAddUser: "Add user (demo).",
    toastAddRule: "Add routing rule (demo).",
    toastPii: "PII redaction is enforced (demo).",
    toastSaved: "Settings saved (demo).",
  },
  vi: {
    intro: "Cấu hình vai trò, quyền, định tuyến và hành vi hệ thống. Các thay đổi ở đây chỉ là demo.",
    adminUsers: "Người dùng quản trị",
    addUser: "+ Thêm người dùng",
    name: "Tên",
    role: "Vai trò",
    department: "Phòng ban",
    status: "Trạng thái",
    active: "Hoạt động",
    disabled: "Đã vô hiệu hoá",
    rbac: "Vai trò & Quyền (RBAC)",
    allowed: "được phép",
    denied: "bị từ chối",
    routingRules: "Quy tắc định tuyến",
    addRule: "+ Thêm quy tắc",
    questionCategory: "Loại câu hỏi",
    routesToDepartment: "Chuyển đến phòng ban",
    notificationPreferences: "Tùy chọn thông báo",
    dailyDigest: "Tổng hợp hằng ngày",
    dailyDigestSub: "Tóm tắt câu hỏi mới chưa giải quyết",
    urgentAlerts: "Cảnh báo khẩn",
    urgentAlertsSub: "Phiếu ưu tiên cao & lỗi lập chỉ mục",
    ticketReplies: "Phản hồi phiếu",
    ticketRepliesSub: "Khi sinh viên phản hồi",
    weeklyAnalytics: "Phân tích hằng tuần",
    weeklyAnalyticsSub: "Báo cáo chất lượng Vinnie",
    dataSourceSettings: "Cài đặt dữ liệu & nguồn",
    recrawlFrequency: "Tần suất thu thập lại",
    optDaily: "Hằng ngày",
    optWeekly: "Hằng tuần",
    optMonthly: "Hằng tháng",
    optManual: "Chỉ thủ công",
    chatLogRetention: "Thời gian lưu nhật ký chat (ngày)",
    redactPii: "Ẩn thông tin cá nhân trong nhật ký",
    maskIdentifiers: "Che định danh sinh viên",
    redactPiiLabel: "Ẩn thông tin cá nhân",
    generalAccess: "Chung & Kiểm soát truy cập",
    systemLanguage: "Ngôn ngữ hệ thống",
    maintenanceMode: "Chế độ bảo trì",
    disablePortal: "Tắt quyền truy cập cổng sinh viên",
    saveChanges: "Lưu thay đổi",
    modules: { tickets: "Phiếu", kb: "Kho tri thức", context: "Ngữ cảnh", settings: "Cài đặt" },
    toastAddUser: "Thêm người dùng (demo).",
    toastAddRule: "Thêm quy tắc định tuyến (demo).",
    toastPii: "Đã bật ẩn thông tin cá nhân (demo).",
    toastSaved: "Đã lưu cài đặt (demo).",
  },
};

function Switch({ checked, onChange, label }: { checked: boolean; onChange: () => void; label: string }) {
  return (
    <label className="ah-switch" aria-label={label}>
      <input type="checkbox" checked={checked} onChange={onChange} />
      <span className="ah-switch-track"><span className="ah-switch-thumb" /></span>
    </label>
  );
}

export default function AdminSettingsPage() {
  const { lang } = usePortal();
  const s = STR[lang];
  const [users] = useState<User[]>(SEED_USERS);
  const [perms, setPerms] = useState(SEED_PERMS);
  const [routing] = useState(SEED_ROUTING);
  const [notif, setNotif] = useState({ digest: true, urgent: true, ticketReply: true, weekly: false });
  const [crawlFreq, setCrawlFreq] = useState("weekly");
  const [retention, setRetention] = useState("365");
  const [language, setLanguage] = useState("en");
  const [maintenance, setMaintenance] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const togglePerm = (role: string, mod: Module) =>
    setPerms((cur) => ({ ...cur, [role]: { ...cur[role], [mod]: !cur[role][mod] } }));

  return (
    <div className="page-inner">
      <p className="field-hint" style={{ margin: "0 0 16px" }}>
        {s.intro}
      </p>

      <div className="aset-sections">
        {/* Admin Users */}
        <div className="acard">
          <div className="acard-head">
            <h2 className="acard-title">{s.adminUsers}</h2>
            <button className="btn btn-outline btn-sm" onClick={() => setToast(s.toastAddUser)}>{s.addUser}</button>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>{s.name}</th><th>{s.role}</th><th>{s.department}</th><th>{s.status}</th></tr></thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.name}>
                    <td className="td-strong">{u.name}</td>
                    <td>{u.role}</td>
                    <td className="td-sub">{u.department}</td>
                    <td><span className={`ah-chip ${u.active ? "success" : "neutral"}`}>{u.active ? s.active : s.disabled}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Roles & Permissions */}
        <div className="acard">
          <div className="acard-head"><h2 className="acard-title">{s.rbac}</h2></div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr><th>{s.role}</th>{MODULE_KEYS.map((m) => <th key={m}>{s.modules[m]}</th>)}</tr>
              </thead>
              <tbody>
                {ROLES.map((role) => (
                  <tr key={role}>
                    <td className="td-strong">{role}</td>
                    {MODULE_KEYS.map((m) => {
                      const on = perms[role][m];
                      return (
                        <td key={m}>
                          <button className={`perm-cell ${on ? "on" : ""}`} aria-label={`${role} ${s.modules[m]} ${on ? s.allowed : s.denied}`} onClick={() => togglePerm(role, m)}>
                            {on ? <IconCheck size={16} /> : "—"}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Routing Rules */}
        <div className="acard">
          <div className="acard-head">
            <h2 className="acard-title">{s.routingRules}</h2>
            <button className="btn btn-outline btn-sm" onClick={() => setToast(s.toastAddRule)}>{s.addRule}</button>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>{s.questionCategory}</th><th>{s.routesToDepartment}</th></tr></thead>
              <tbody>
                {routing.map((r) => (
                  <tr key={r.category}><td className="td-strong">{r.category}</td><td>→ {r.department}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="aset-grid2">
          {/* Notification preferences */}
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">{s.notificationPreferences}</h2></div>
            <div className="aset-row">
              <div><div className="aset-row-label">{s.dailyDigest}</div><div className="aset-row-sub">{s.dailyDigestSub}</div></div>
              <Switch checked={notif.digest} onChange={() => setNotif((n) => ({ ...n, digest: !n.digest }))} label={s.dailyDigest} />
            </div>
            <div className="aset-row">
              <div><div className="aset-row-label">{s.urgentAlerts}</div><div className="aset-row-sub">{s.urgentAlertsSub}</div></div>
              <Switch checked={notif.urgent} onChange={() => setNotif((n) => ({ ...n, urgent: !n.urgent }))} label={s.urgentAlerts} />
            </div>
            <div className="aset-row">
              <div><div className="aset-row-label">{s.ticketReplies}</div><div className="aset-row-sub">{s.ticketRepliesSub}</div></div>
              <Switch checked={notif.ticketReply} onChange={() => setNotif((n) => ({ ...n, ticketReply: !n.ticketReply }))} label={s.ticketReplies} />
            </div>
            <div className="aset-row">
              <div><div className="aset-row-label">{s.weeklyAnalytics}</div><div className="aset-row-sub">{s.weeklyAnalyticsSub}</div></div>
              <Switch checked={notif.weekly} onChange={() => setNotif((n) => ({ ...n, weekly: !n.weekly }))} label={s.weeklyAnalytics} />
            </div>
          </div>

          {/* Data & source settings */}
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">{s.dataSourceSettings}</h2></div>
            <div className="field">
              <label className="field-label" htmlFor="set-crawl">{s.recrawlFrequency}</label>
              <select id="set-crawl" className="select" value={crawlFreq} onChange={(e) => setCrawlFreq(e.target.value)}>
                <option value="daily">{s.optDaily}</option>
                <option value="weekly">{s.optWeekly}</option>
                <option value="monthly">{s.optMonthly}</option>
                <option value="manual">{s.optManual}</option>
              </select>
            </div>
            <div className="field" style={{ marginTop: 12 }}>
              <label className="field-label" htmlFor="set-retention">{s.chatLogRetention}</label>
              <input id="set-retention" type="number" className="input" value={retention} onChange={(e) => setRetention(e.target.value)} />
            </div>
            <div className="aset-row" style={{ marginTop: 4 }}>
              <div><div className="aset-row-label">{s.redactPii}</div><div className="aset-row-sub">{s.maskIdentifiers}</div></div>
              <Switch checked onChange={() => setToast(s.toastPii)} label={s.redactPiiLabel} />
            </div>
          </div>
        </div>

        {/* General / access control */}
        <div className="acard">
          <div className="acard-head"><h2 className="acard-title">{s.generalAccess}</h2></div>
          <div className="aset-grid2">
            <div className="field">
              <label className="field-label" htmlFor="set-lang">{s.systemLanguage}</label>
              <select id="set-lang" className="select" value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="en">English (US)</option>
                <option value="vi">Tiếng Việt</option>
              </select>
            </div>
            <div className="aset-row" style={{ borderBottom: "none", alignItems: "flex-start" }}>
              <div><div className="aset-row-label">{s.maintenanceMode}</div><div className="aset-row-sub">{s.disablePortal}</div></div>
              <Switch checked={maintenance} onChange={() => setMaintenance((m) => !m)} label={s.maintenanceMode} />
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-primary" onClick={() => setToast(s.toastSaved)}>
              <IconCheck size={14} /> {s.saveChanges}
            </button>
          </div>
        </div>
      </div>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
