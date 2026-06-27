# Phase 12B Forum Write Workflow And Moderation

Phase 12B extends the real forum foundation with authenticated topic creation,
comments/replies, owner edits, soft deletes, and basic moderator actions. FastAPI remains
the only database access layer; the frontend still talks only to API routes/proxy paths.

## Endpoints

Student-safe write endpoints:

- `POST /forum/topics`
- `PATCH /forum/topics/{topic_id}`
- `DELETE /forum/topics/{topic_id}`
- `POST /forum/topics/{topic_id}/comments`
- `PATCH /forum/comments/{comment_id}`
- `DELETE /forum/comments/{comment_id}`

Basic moderation endpoints:

- `POST /forum/topics/{topic_id}/pin`
- `POST /forum/topics/{topic_id}/unpin`
- `POST /forum/topics/{topic_id}/lock`
- `POST /forum/topics/{topic_id}/unlock`
- `POST /forum/topics/{topic_id}/archive`
- `POST /forum/comments/{comment_id}/hide`
- `POST /forum/comments/{comment_id}/unhide`

Existing Phase 12A read endpoints continue to work:

- `GET /forum/categories`
- `GET /forum/topics`
- `GET /forum/topics/{topic_id}`
- `GET /forum/topics/{topic_id}/comments`

## Permissions

- Anonymous users receive `401` for forum write actions.
- Students can create topics and comments.
- Students can edit or soft-delete only their own topic/comment.
- Students cannot edit/delete content on locked topics.
- Locked topics reject new student comments.
- `global_admin`, `institute_admin`, and `staff` can moderate topics/comments.
- Forum schema does not yet carry institute visibility, so institute admin/staff moderation uses
  the existing admin role pattern rather than institute-scoped forum filtering.

## Moderation Behavior

- Pin/unpin changes topic ordering because pinned topics sort above regular topics.
- Lock/unlock controls whether students can add replies.
- Archive uses the existing `forum_topics.deleted` soft-delete flag.
- Hide/unhide uses the existing `forum_comments.deleted` soft-delete flag.
- Archived topics are hidden from normal topic lists.
- Hidden comments render as removed placeholders in existing comment trees.

## Frontend

The existing forum UI now uses the real write APIs:

- Students can create topics from `/student/forum`.
- Students can reply and edit/delete their own comments from topic detail.
- Students can edit/delete their own unlocked topics from topic detail.
- Admin/staff users see moderator controls for pin, lock, archive, hide, and unhide.
- Locked topics show the existing locked banner and disable reply controls.

## Known Limitations

Phase 12B intentionally avoids full moderation queues, reputation, advanced reporting workflows,
institute-scoped forum visibility, rich edit history, and hard deletes. Those remain candidates
for Phase 12C and later.

## Verification

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
(cd frontend && npm run typecheck)
```
