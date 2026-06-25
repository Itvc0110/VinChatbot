"use client";

import { useState } from "react";
import { Toast } from "@/components/ui/primitives";
import { IconCheck } from "@/components/shell/icons";

// Admin System Settings (Phase 4, new route). Demo-only: there is no settings backend, so all controls
// are local demo state. No live API / auth / RBAC logic is wired — this is a presentational scaffold.

interface User { name: string; role: string; department: string; active: boolean }
type Module = "tickets" | "kb" | "context" | "settings";
const MODULES: { key: Module; label: string }[] = [
  { key: "tickets", label: "Tickets" },
  { key: "kb", label: "Knowledge Base" },
  { key: "context", label: "Context" },
  { key: "settings", label: "Settings" },
];
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

function Switch({ checked, onChange, label }: { checked: boolean; onChange: () => void; label: string }) {
  return (
    <label className="ah-switch" aria-label={label}>
      <input type="checkbox" checked={checked} onChange={onChange} />
      <span className="ah-switch-track"><span className="ah-switch-thumb" /></span>
    </label>
  );
}

export default function AdminSettingsPage() {
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
        Configure roles, permissions, routing, and system behavior. Changes here are demo-only.
      </p>

      <div className="aset-sections">
        {/* Admin Users */}
        <div className="acard">
          <div className="acard-head">
            <h2 className="acard-title">Admin Users</h2>
            <button className="btn btn-outline btn-sm" onClick={() => setToast("Add user (demo).")}>+ Add User</button>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Name</th><th>Role</th><th>Department</th><th>Status</th></tr></thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.name}>
                    <td className="td-strong">{u.name}</td>
                    <td>{u.role}</td>
                    <td className="td-sub">{u.department}</td>
                    <td><span className={`ah-chip ${u.active ? "success" : "neutral"}`}>{u.active ? "Active" : "Disabled"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Roles & Permissions */}
        <div className="acard">
          <div className="acard-head"><h2 className="acard-title">Roles &amp; Permissions (RBAC)</h2></div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr><th>Role</th>{MODULES.map((m) => <th key={m.key}>{m.label}</th>)}</tr>
              </thead>
              <tbody>
                {ROLES.map((role) => (
                  <tr key={role}>
                    <td className="td-strong">{role}</td>
                    {MODULES.map((m) => {
                      const on = perms[role][m.key];
                      return (
                        <td key={m.key}>
                          <button className={`perm-cell ${on ? "on" : ""}`} aria-label={`${role} ${m.label} ${on ? "allowed" : "denied"}`} onClick={() => togglePerm(role, m.key)}>
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
            <h2 className="acard-title">Routing Rules</h2>
            <button className="btn btn-outline btn-sm" onClick={() => setToast("Add routing rule (demo).")}>+ Add Rule</button>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Question category</th><th>Routes to department</th></tr></thead>
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
            <div className="acard-head"><h2 className="acard-title">Notification Preferences</h2></div>
            <div className="aset-row">
              <div><div className="aset-row-label">Daily digest</div><div className="aset-row-sub">Summary of new unresolved questions</div></div>
              <Switch checked={notif.digest} onChange={() => setNotif((n) => ({ ...n, digest: !n.digest }))} label="Daily digest" />
            </div>
            <div className="aset-row">
              <div><div className="aset-row-label">Urgent alerts</div><div className="aset-row-sub">High-priority tickets &amp; indexing failures</div></div>
              <Switch checked={notif.urgent} onChange={() => setNotif((n) => ({ ...n, urgent: !n.urgent }))} label="Urgent alerts" />
            </div>
            <div className="aset-row">
              <div><div className="aset-row-label">Ticket replies</div><div className="aset-row-sub">When a student responds</div></div>
              <Switch checked={notif.ticketReply} onChange={() => setNotif((n) => ({ ...n, ticketReply: !n.ticketReply }))} label="Ticket replies" />
            </div>
            <div className="aset-row">
              <div><div className="aset-row-label">Weekly analytics</div><div className="aset-row-sub">Vinnie quality report</div></div>
              <Switch checked={notif.weekly} onChange={() => setNotif((n) => ({ ...n, weekly: !n.weekly }))} label="Weekly analytics" />
            </div>
          </div>

          {/* Data & source settings */}
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">Data &amp; Source Settings</h2></div>
            <div className="field">
              <label className="field-label" htmlFor="set-crawl">Re-crawl frequency</label>
              <select id="set-crawl" className="select" value={crawlFreq} onChange={(e) => setCrawlFreq(e.target.value)}>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
                <option value="manual">Manual only</option>
              </select>
            </div>
            <div className="field" style={{ marginTop: 12 }}>
              <label className="field-label" htmlFor="set-retention">Chat log retention (days)</label>
              <input id="set-retention" type="number" className="input" value={retention} onChange={(e) => setRetention(e.target.value)} />
            </div>
            <div className="aset-row" style={{ marginTop: 4 }}>
              <div><div className="aset-row-label">Redact PII in logs</div><div className="aset-row-sub">Mask student identifiers</div></div>
              <Switch checked onChange={() => setToast("PII redaction is enforced (demo).")} label="Redact PII" />
            </div>
          </div>
        </div>

        {/* General / access control */}
        <div className="acard">
          <div className="acard-head"><h2 className="acard-title">General &amp; Access Control</h2></div>
          <div className="aset-grid2">
            <div className="field">
              <label className="field-label" htmlFor="set-lang">System language</label>
              <select id="set-lang" className="select" value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="en">English (US)</option>
                <option value="vi">Tiếng Việt</option>
              </select>
            </div>
            <div className="aset-row" style={{ borderBottom: "none", alignItems: "flex-start" }}>
              <div><div className="aset-row-label">Maintenance mode</div><div className="aset-row-sub">Disable student portal access</div></div>
              <Switch checked={maintenance} onChange={() => setMaintenance((m) => !m)} label="Maintenance mode" />
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-primary" onClick={() => setToast("Settings saved (demo).")}>
              <IconCheck size={14} /> Save changes
            </button>
          </div>
        </div>
      </div>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
