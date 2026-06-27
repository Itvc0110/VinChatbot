"use client";

import { useEffect, useMemo, useState } from "react";
import { AsyncBoundary, EmptyState, Toast } from "@/components/ui/primitives";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { useAuth } from "@/lib/auth";
import {
  archiveAdminNotification,
  createNotification,
  getAdminNotificationTargets,
  getAdminNotifications,
  publishNotification,
  scheduleNotification,
  updateNotification,
  type BackendAdminNotificationTarget,
} from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type {
  Notification,
  NotificationPriority,
  NotificationStatus,
  NotificationType,
} from "@/lib/portalTypes";
import { IconBell, IconCheck } from "@/components/shell/icons";

const CATEGORIES: NotificationType[] = [
  "academic",
  "schedule",
  "deadline",
  "event",
  "student_services",
  "system",
];
const PRIORITIES: NotificationPriority[] = ["low", "medium", "high", "urgent"];
const STATUS_CHIP: Record<NotificationStatus, string> = {
  published: "success",
  scheduled: "info",
  draft: "neutral",
  archived: "neutral",
};

const STR = {
  en: {
    allStudents: "All students",
    institute: "Institute",
    targetScope: "Target",
    scheduleAt: "Publish at",
    activeUntil: "Active until",
    edit: "Edit",
    cancelEdit: "Cancel edit",
    saveChanges: "Save changes",
    publishNow: "Publish now",
    schedule: "Schedule",
    archive: "Archive",
    scheduledToast: "Notification scheduled.",
    archivedToast: "Notification archived.",
    updatedToast: "Notification updated.",
    targetRequired: "Select an institute target.",
    titleRequired: "Enter a notification title.",
    messageRequired: "Enter the notification message.",
    scheduleRequired: "Choose a publish time.",
    invalidDateRange: "Active-until date must be after the publish time.",
    confirmPublish: "Publish this notification now?",
    confirmArchive: "Archive this notification? Students will no longer see it.",
    empty: "No notifications yet",
    preview: "Preview",
    previewTitle: "Notification title",
    previewMsg: "Your message preview appears here as students will see it.",
    statusLabels: {
      draft: "Draft",
      scheduled: "Scheduled",
      published: "Published",
      archived: "Archived",
    },
  },
  vi: {
    allStudents: "Tất cả sinh viên",
    institute: "Viện",
    targetScope: "Đối tượng",
    scheduleAt: "Thời điểm đăng",
    activeUntil: "Hiển thị đến",
    edit: "Sửa",
    cancelEdit: "Hủy sửa",
    saveChanges: "Lưu thay đổi",
    publishNow: "Đăng ngay",
    schedule: "Lên lịch",
    archive: "Lưu trữ",
    scheduledToast: "Đã lên lịch thông báo.",
    archivedToast: "Đã lưu trữ thông báo.",
    updatedToast: "Đã cập nhật thông báo.",
    targetRequired: "Chọn viện nhận thông báo.",
    titleRequired: "Nhập tiêu đề thông báo.",
    messageRequired: "Nhập nội dung thông báo.",
    scheduleRequired: "Chọn thời điểm đăng.",
    invalidDateRange: "Ngày kết thúc phải sau thời điểm đăng.",
    confirmPublish: "Đăng thông báo này ngay?",
    confirmArchive: "Lưu trữ thông báo này? Sinh viên sẽ không còn thấy thông báo.",
    empty: "Chưa có thông báo",
    preview: "Xem trước",
    previewTitle: "Tiêu đề thông báo",
    previewMsg: "Bản xem trước nội dung của bạn hiển thị tại đây như sinh viên sẽ thấy.",
    statusLabels: {
      draft: "Bản nháp",
      scheduled: "Đã lên lịch",
      published: "Đã đăng",
      archived: "Đã lưu trữ",
    },
  },
} as const;

function toDateInput(value?: string): string {
  if (!value) return "";
  return value.slice(0, 10);
}

function toDateTimeLocal(value?: string): string {
  if (!value) return "";
  return value.slice(0, 16);
}

function localToIso(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function dateInputToIso(value: string): string | null {
  return value ? new Date(`${value}T00:00:00`).toISOString() : null;
}

function dateInputToEndOfDayIso(value: string): string | null {
  return value ? new Date(`${value}T23:59:59`).toISOString() : null;
}

export default function AdminNotificationsPage() {
  const { p, lang } = usePortal();
  const { token } = useAuth();
  const s = STR[lang];
  const loaded = useAsync(getAdminNotifications, [token]);
  const targetsLoaded = useAsync(getAdminNotificationTargets, [token]);

  const [items, setItems] = useState<Notification[] | null>(null);
  const [targets, setTargets] = useState<BackendAdminNotificationTarget[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [category, setCategory] = useState<NotificationType>("deadline");
  const [priority, setPriority] = useState<NotificationPriority>("medium");
  const [targetScope, setTargetScope] = useState<"all" | "institute">("all");
  const [instituteId, setInstituteId] = useState("");
  const [eventDate, setEventDate] = useState("");
  const [deadline, setDeadline] = useState("");
  const [scheduleAt, setScheduleAt] = useState("");
  const [endDate, setEndDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [formErrors, setFormErrors] = useState<string[]>([]);

  useEffect(() => {
    setItems(null);
    setTargets([]);
    setToast(null);
    resetForm();
    setBusy(false);
    setFormErrors([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (loaded.status === "success") setItems(loaded.data);
  }, [loaded.status, loaded.status === "success" ? loaded.data : null]);

  useEffect(() => {
    if (targetsLoaded.status === "success") {
      setTargets(targetsLoaded.data);
      if (targetsLoaded.data.length === 1) {
        setInstituteId(targetsLoaded.data[0].id);
      }
    }
  }, [targetsLoaded.status, targetsLoaded.status === "success" ? targetsLoaded.data : null]);

  const all = items ?? [];
  const selectedTarget = useMemo(
    () => targets.find((target) => target.id === instituteId),
    [instituteId, targets]
  );
  const targetInvalid = targetScope === "institute" && !instituteId;
  const dateRangeInvalid = (() => {
    const publishAt = localToIso(scheduleAt);
    const activeUntil = dateInputToEndOfDayIso(endDate);
    return !!publishAt && !!activeUntil && new Date(activeUntil) < new Date(publishAt);
  })();

  function resetForm() {
    setEditingId(null);
    setTitle("");
    setMessage("");
    setCategory("deadline");
    setPriority("medium");
    setTargetScope("all");
    setInstituteId("");
    setEventDate("");
    setDeadline("");
    setScheduleAt("");
    setEndDate("");
    setFormErrors([]);
  }

  function editNotification(notification: Notification) {
    setEditingId(notification.id);
    setTitle(notification.title);
    setMessage(notification.message);
    setCategory(notification.type);
    setPriority(notification.priority ?? "medium");
    const audience = notification.target_audience?.[0];
    const target = targets.find((item) => item.code === audience);
    setTargetScope(target ? "institute" : "all");
    setInstituteId(target?.id ?? "");
    setEventDate(toDateInput(notification.event_date));
    setDeadline(toDateInput(notification.deadline));
    setScheduleAt(toDateTimeLocal(notification.start_date));
    setEndDate(toDateInput(notification.end_date));
  }

  function upsertItem(notification: Notification) {
    setItems((cur) => {
      const existing = cur ?? [];
      if (existing.some((item) => item.id === notification.id)) {
        return existing.map((item) => (item.id === notification.id ? notification : item));
      }
      return [notification, ...existing];
    });
  }

  function payload(status?: NotificationStatus) {
    return {
      title: title.trim(),
      message: message.trim(),
      type: category,
      priority,
      status,
      target_scope: targetScope,
      institute_id: targetScope === "institute" ? instituteId : null,
      deadline: dateInputToIso(deadline),
      event_date: dateInputToIso(eventDate),
      start_date: localToIso(scheduleAt),
      end_date: dateInputToEndOfDayIso(endDate),
    };
  }

  function validateForm(options: { requireSchedule?: boolean } = {}): boolean {
    const errors: string[] = [];
    if (!title.trim()) errors.push(s.titleRequired);
    if (!message.trim()) errors.push(s.messageRequired);
    if (targetInvalid) errors.push(s.targetRequired);
    if (options.requireSchedule && !localToIso(scheduleAt)) errors.push(s.scheduleRequired);
    if (dateRangeInvalid) errors.push(s.invalidDateRange);
    setFormErrors(errors);
    return errors.length === 0;
  }

  async function saveDraft() {
    if (!validateForm()) return;
    setBusy(true);
    try {
      const saved = editingId
        ? await updateNotification(editingId, payload())
        : await createNotification(payload("draft"));
      upsertItem(saved);
      setToast(editingId ? s.updatedToast : p.adminNotif.draftCreated);
      resetForm();
    } catch {
      setToast(p.adminNotif.actionFailed);
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    if (!validateForm() || !window.confirm(s.confirmPublish)) return;
    setBusy(true);
    try {
      const notification = editingId
        ? await updateNotification(editingId, payload())
        : await createNotification(payload("draft"));
      const published = await publishNotification(notification.id);
      upsertItem(published);
      setToast(p.adminNotif.publishedToast);
      resetForm();
    } catch {
      setToast(p.adminNotif.actionFailed);
    } finally {
      setBusy(false);
    }
  }

  async function schedule() {
    const publishAt = localToIso(scheduleAt);
    if (!validateForm({ requireSchedule: true }) || !publishAt) return;
    setBusy(true);
    try {
      const notification = editingId
        ? await updateNotification(editingId, payload())
        : await createNotification(payload("draft"));
      const scheduled = await scheduleNotification(
        notification.id,
        publishAt,
        dateInputToEndOfDayIso(endDate)
      );
      upsertItem(scheduled);
      setToast(s.scheduledToast);
      resetForm();
    } catch {
      setToast(p.adminNotif.actionFailed);
    } finally {
      setBusy(false);
    }
  }

  async function archive(id: string) {
    if (!window.confirm(s.confirmArchive)) return;
    setBusy(true);
    try {
      const archived = await archiveAdminNotification(id);
      upsertItem(archived);
      setToast(s.archivedToast);
    } catch {
      setToast(p.adminNotif.actionFailed);
    } finally {
      setBusy(false);
    }
  }

  async function publishExisting(id: string) {
    if (!window.confirm(s.confirmPublish)) return;
    setBusy(true);
    try {
      const published = await publishNotification(id);
      upsertItem(published);
      setToast(p.adminNotif.publishedToast);
    } catch {
      setToast(p.adminNotif.actionFailed);
    } finally {
      setBusy(false);
    }
  }

  function targetLabel(notification: Notification): string {
    const audience = notification.target_audience ?? [];
    if (audience.length === 0 || audience[0] === "all") return s.allStudents;
    return audience.join(", ");
  }

  return (
    <div className="page-inner">
      <div className="anotif-grid">
        <div>
          <div className="acard-head">
            <h2 className="acard-title">{p.adminNotif.listHeading}</h2>
          </div>
          <AsyncBoundary state={loaded} onRetry={loaded.reload}>
            {() =>
              all.length === 0 ? (
                <EmptyState icon={<IconBell size={28} />} title={s.empty} />
              ) : (
                <div className="anotif-list">
                  {all.map((n) => {
                    const st = n.status ?? "published";
                    return (
                      <div key={n.id} className="anotif-card">
                        <div className="anotif-card-top">
                          <span className={`ah-chip ${STATUS_CHIP[st] ?? "neutral"}`}>
                            {s.statusLabels[st] ?? st}
                          </span>
                          <span className="ah-chip neutral">{p.enums.notificationType[n.type]}</span>
                          <span className="ah-chip info">{targetLabel(n)}</span>
                          <span className="anotif-card-time">
                            {relativeTime(n.updated_at ?? n.created_at, lang)}
                          </span>
                        </div>
                        <h3 className="anotif-card-title">{n.title}</h3>
                        <p className="anotif-card-msg">{n.message}</p>
                        <div className="review-actions">
                          <button className="btn btn-outline btn-sm" type="button" onClick={() => editNotification(n)}>
                            {s.edit}
                          </button>
                          {st !== "published" && st !== "archived" && (
                            <button
                              className="btn btn-primary btn-sm"
                              type="button"
                              disabled={busy}
                              onClick={() => void publishExisting(n.id)}
                            >
                              {s.publishNow}
                            </button>
                          )}
                          {st !== "archived" && (
                            <button className="btn btn-ghost btn-sm" type="button" disabled={busy} onClick={() => void archive(n.id)}>
                              {s.archive}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )
            }
          </AsyncBoundary>
        </div>

        <div className="anotif-composer">
          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">
                {editingId ? s.edit : p.adminNotif.createHeading}
              </h2>
            </div>
            <div className="form-grid">
              <div className="field">
                <label className="field-label" htmlFor="n-title">{p.adminNotif.fTitle}</label>
                <input id="n-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder={p.adminNotif.fTitlePlaceholder} />
              </div>
              <div className="field">
                <label className="field-label" htmlFor="n-message">{p.adminNotif.fMessage}</label>
                <textarea id="n-message" className="textarea" value={message} onChange={(e) => setMessage(e.target.value)} placeholder={p.adminNotif.fMessagePlaceholder} />
              </div>

              <div className="grid cols-2" style={{ gap: 12 }}>
                <div className="field">
                  <label className="field-label" htmlFor="n-category">{p.adminNotif.fCategory}</label>
                  <select id="n-category" className="select" value={category} onChange={(e) => setCategory(e.target.value as NotificationType)}>
                    {CATEGORIES.map((c) => <option key={c} value={c}>{p.enums.notificationType[c]}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="n-priority">{p.adminNotif.fPriority}</label>
                  <select id="n-priority" className="select" value={priority} onChange={(e) => setPriority(e.target.value as NotificationPriority)}>
                    {PRIORITIES.map((pr) => <option key={pr} value={pr}>{pr}</option>)}
                  </select>
                </div>
              </div>

              <div className="grid cols-2" style={{ gap: 12 }}>
                <div className="field">
                  <label className="field-label" htmlFor="n-target">{s.targetScope}</label>
                  <select id="n-target" className="select" value={targetScope} onChange={(e) => setTargetScope(e.target.value as "all" | "institute")}>
                    <option value="all">{s.allStudents}</option>
                    <option value="institute">{s.institute}</option>
                  </select>
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="n-institute">{s.institute}</label>
                  <select id="n-institute" className="select" value={instituteId} disabled={targetScope !== "institute" || targetsLoaded.status === "loading"} onChange={(e) => setInstituteId(e.target.value)}>
                    <option value="">{selectedTarget?.code ?? "—"}</option>
                    {targets.map((target) => <option key={target.id} value={target.id}>{target.code}</option>)}
                  </select>
                  {targetInvalid && <p className="td-sub">{s.targetRequired}</p>}
                  {targetsLoaded.status === "error" && <p className="td-sub">{p.adminNotif.actionFailed}</p>}
                </div>
              </div>

              <div className="grid cols-2" style={{ gap: 12 }}>
                <div className="field">
                  <label className="field-label" htmlFor="n-deadline">{p.adminNotif.fDeadline}</label>
                  <input id="n-deadline" type="date" className="input" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="n-event">{p.adminNotif.fEventDate}</label>
                  <input id="n-event" type="date" className="input" value={eventDate} onChange={(e) => setEventDate(e.target.value)} />
                </div>
              </div>

              <div className="grid cols-2" style={{ gap: 12 }}>
                <div className="field">
                  <label className="field-label" htmlFor="n-schedule">{s.scheduleAt}</label>
                  <input id="n-schedule" type="datetime-local" className="input" value={scheduleAt} onChange={(e) => setScheduleAt(e.target.value)} />
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="n-end">{s.activeUntil}</label>
                  <input id="n-end" type="date" className="input" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
                  {dateRangeInvalid && <p className="td-sub">{s.invalidDateRange}</p>}
                </div>
              </div>

              {formErrors.length > 0 && (
                <div className="confirm-row" role="alert">
                  <span>{formErrors[0]}</span>
                </div>
              )}

              <div className="review-actions">
                {editingId && (
                  <button className="btn btn-ghost" type="button" onClick={resetForm}>
                    {s.cancelEdit}
                  </button>
                )}
                <button
                  className="btn btn-outline"
                  type="button"
                  onClick={() => void saveDraft()}
                  disabled={busy}
                >
                  {editingId ? s.saveChanges : p.adminNotif.saveDraftBtn}
                </button>
                <button
                  className="btn btn-outline"
                  type="button"
                  onClick={() => void schedule()}
                  disabled={busy}
                >
                  {s.schedule}
                </button>
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={() => void publish()}
                  disabled={busy}
                >
                  <IconCheck size={15} /> {busy ? p.adminNotif.publishing : s.publishNow}
                </button>
              </div>
            </div>
          </div>

          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">{s.preview}</h2></div>
            <div className="anotif-preview-frame">
              <div className="anotif-preview-card">
                <span className="anotif-preview-ic"><IconBell size={16} /></span>
                <div style={{ minWidth: 0 }}>
                  <div className="anotif-preview-title">{title.trim() || s.previewTitle}</div>
                  <div className="anotif-preview-msg">{message.trim() || s.previewMsg}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
