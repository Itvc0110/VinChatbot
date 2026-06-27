-- Forum / Discussion Hub (public peer discussion, separate from private tickets).
-- Adds forum entities and extends the existing notifications table with a per-user
-- recipient path (completing the already-anticipated target_scope = 'student') so that
-- @mention / reply notifications surface in the existing notification bell + page.

create table if not exists forum_categories (
    id uuid primary key default gen_random_uuid(),
    slug text not null unique,
    name_en text not null,
    name_vi text not null,
    description_en text,
    description_vi text,
    color text not null default '#0057a8',
    sort_order integer not null default 0,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists forum_topics (
    id uuid primary key default gen_random_uuid(),
    category_id uuid not null references forum_categories(id) on delete restrict,
    author_user_id uuid references users(id) on delete set null,
    title text not null,
    content text not null,
    tags text[] not null default '{}',
    attachments jsonb not null default '[]'::jsonb,
    is_pinned boolean not null default false,
    is_locked boolean not null default false,
    -- FK to forum_comments added after that table exists (circular dependency).
    official_comment_id uuid,
    view_count integer not null default 0,
    deleted boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    last_activity_at timestamptz not null default now(),
    constraint forum_topics_view_count_check check (view_count >= 0)
);

create table if not exists forum_comments (
    id uuid primary key default gen_random_uuid(),
    topic_id uuid not null references forum_topics(id) on delete cascade,
    author_user_id uuid references users(id) on delete set null,
    parent_comment_id uuid references forum_comments(id) on delete cascade,
    content text not null,
    is_official boolean not null default false,
    deleted boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- forum_topics.official_comment_id -> forum_comments(id): created here now that the
-- referenced table exists. on delete set null so deleting the official answer just clears it.
alter table forum_topics
    drop constraint if exists forum_topics_official_comment_fk;
alter table forum_topics
    add constraint forum_topics_official_comment_fk
    foreign key (official_comment_id) references forum_comments(id) on delete set null;

-- Polymorphic vote table for both topics and comments. target_id has no FK because it can
-- point at either entity; the (user, target_type, target_id) unique key enforces one vote each.
create table if not exists forum_votes (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    target_type text not null,
    target_id uuid not null,
    value smallint not null,
    created_at timestamptz not null default now(),
    unique (user_id, target_type, target_id),
    constraint forum_votes_target_type_check check (target_type in ('topic', 'comment')),
    constraint forum_votes_value_check check (value in (-1, 1))
);

create table if not exists forum_mentions (
    id uuid primary key default gen_random_uuid(),
    topic_id uuid references forum_topics(id) on delete cascade,
    comment_id uuid references forum_comments(id) on delete cascade,
    mentioned_user_id uuid not null references users(id) on delete cascade,
    created_by uuid references users(id) on delete set null,
    created_at timestamptz not null default now(),
    constraint forum_mentions_target_check check (
        topic_id is not null or comment_id is not null
    )
);

create table if not exists forum_reports (
    id uuid primary key default gen_random_uuid(),
    reporter_user_id uuid references users(id) on delete set null,
    target_type text not null,
    target_id uuid not null,
    reason text not null,
    status text not null default 'open',
    resolved_by uuid references users(id) on delete set null,
    resolved_at timestamptz,
    created_at timestamptz not null default now(),
    constraint forum_reports_target_type_check check (target_type in ('topic', 'comment')),
    constraint forum_reports_status_check check (status in ('open', 'resolved', 'dismissed'))
);

-- Extend notifications for per-user forum notifications. The original schema already allows
-- target_scope = 'student' but had no recipient column; this completes that design.
alter table notifications
    add column if not exists recipient_user_id uuid references users(id) on delete cascade;
alter table notifications
    add column if not exists forum_topic_id uuid references forum_topics(id) on delete cascade;
alter table notifications
    add column if not exists forum_comment_id uuid references forum_comments(id) on delete cascade;

alter table notifications
    drop constraint if exists notifications_type_check;
alter table notifications
    add constraint notifications_type_check check (
        type in ('announcement', 'deadline', 'event', 'academic', 'system', 'emergency', 'forum')
    );

create index if not exists idx_forum_topics_category_id_last_activity
    on forum_topics(category_id, last_activity_at desc);
create index if not exists idx_forum_topics_author_user_id on forum_topics(author_user_id);
create index if not exists idx_forum_comments_topic_id_created_at
    on forum_comments(topic_id, created_at);
create index if not exists idx_forum_comments_parent_comment_id
    on forum_comments(parent_comment_id);
create index if not exists idx_forum_votes_target on forum_votes(target_type, target_id);
create index if not exists idx_forum_mentions_mentioned_user_id
    on forum_mentions(mentioned_user_id);
create index if not exists idx_forum_reports_status on forum_reports(status, created_at desc);
create index if not exists idx_notifications_recipient_user_id
    on notifications(recipient_user_id);

drop trigger if exists set_forum_topics_updated_at on forum_topics;
create trigger set_forum_topics_updated_at
before update on forum_topics
for each row
execute function set_updated_at();

drop trigger if exists set_forum_comments_updated_at on forum_comments;
create trigger set_forum_comments_updated_at
before update on forum_comments
for each row
execute function set_updated_at();

insert into forum_categories (slug, name_en, name_vi, description_en, description_vi, color, sort_order)
values
    ('general', 'General', 'Tổng quát',
     'Open discussion for the VinUni student community.',
     'Thảo luận chung cho cộng đồng sinh viên VinUni.', '#0057a8', 1),
    ('academics', 'Academics', 'Học thuật',
     'Majors, registration, GPA, advising and academic policy.',
     'Ngành học, đăng ký, GPA, cố vấn và quy định học thuật.', '#7c3aed', 2),
    ('courses', 'Courses', 'Môn học',
     'Course-specific questions, study groups and materials.',
     'Câu hỏi theo môn học, nhóm học tập và tài liệu.', '#0b6bcb', 3),
    ('campus-life', 'Campus Life', 'Đời sống sinh viên',
     'Clubs, events, dorms and everything around campus.',
     'Câu lạc bộ, sự kiện, ký túc xá và đời sống trong trường.', '#10b981', 4),
    ('career', 'Career', 'Nghề nghiệp',
     'Internships, jobs, resumes and career development.',
     'Thực tập, việc làm, CV và phát triển sự nghiệp.', '#b45309', 5),
    ('tech-help', 'Tech Help', 'Hỗ trợ kỹ thuật',
     'Portal, accounts, Wi-Fi and other technical questions.',
     'Cổng thông tin, tài khoản, Wi-Fi và các vấn đề kỹ thuật.', '#64748b', 6)
on conflict (slug) do update
set
    name_en = excluded.name_en,
    name_vi = excluded.name_vi,
    description_en = excluded.description_en,
    description_vi = excluded.description_vi,
    color = excluded.color,
    sort_order = excluded.sort_order;
