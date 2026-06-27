"use client";

import { useState } from "react";
import { usePortal } from "@/lib/portalI18n";
import { IconShield } from "@/components/shell/icons";
import type { ForumTopic } from "@/lib/portalTypes";

export interface TopicModeratePatch {
  is_pinned?: boolean;
  is_locked?: boolean;
  deleted?: boolean;
}

// Inline moderator controls on the topic detail (rendered only for admin/staff). Pin/lock are
// instant toggles; archive uses a two-click confirm to avoid accidents.
export function ModActionBar({
  topic,
  onModerate,
  busy = false,
}: {
  topic: ForumTopic;
  onModerate: (patch: TopicModeratePatch) => void;
  busy?: boolean;
}) {
  const { p } = usePortal();
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <div className="forum-modbar" role="group" aria-label={p.forum.moderator}>
      <span className="forum-modbar-label">
        <IconShield size={15} /> {p.forum.moderator}
      </span>
      <button
        type="button"
        className="btn btn-outline btn-sm"
        onClick={() => onModerate({ is_pinned: !topic.is_pinned })}
        disabled={busy}
      >
        {topic.is_pinned ? p.forum.unpin : p.forum.pin}
      </button>
      <button
        type="button"
        className="btn btn-outline btn-sm"
        onClick={() => onModerate({ is_locked: !topic.is_locked })}
        disabled={busy}
      >
        {topic.is_locked ? p.forum.unlock : p.forum.lock}
      </button>
      {confirmDelete ? (
        <span className="forum-confirm">
          <button
            type="button"
            className="ah-btn-red"
            onClick={() => onModerate({ deleted: true })}
            disabled={busy}
          >
            {p.forum.archive}?
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setConfirmDelete(false)}
            disabled={busy}
          >
            {p.forum.cancel}
          </button>
        </span>
      ) : (
        <button
          type="button"
          className="btn btn-ghost btn-sm forum-danger"
          onClick={() => setConfirmDelete(true)}
          disabled={busy}
        >
          {p.forum.archive}
        </button>
      )}
    </div>
  );
}
