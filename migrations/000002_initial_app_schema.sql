create extension if not exists pgcrypto;

create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    email text not null unique,
    password_hash text,
    full_name text not null,
    preferred_name text,
    phone text,
    avatar_url text,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint users_status_check check (status in ('active', 'inactive', 'suspended'))
);

create table if not exists roles (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null,
    description text
);

create table if not exists user_roles (
    user_id uuid not null references users(id) on delete cascade,
    role_id uuid not null references roles(id) on delete cascade,
    primary key (user_id, role_id)
);

create table if not exists sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    token_hash text not null unique,
    expires_at timestamptz not null,
    created_at timestamptz not null default now(),
    revoked_at timestamptz
);

create table if not exists institutes (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name_vi text not null,
    name_en text not null
);

create table if not exists student_profiles (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique references users(id) on delete cascade,
    student_id text not null unique,
    institute_id uuid not null references institutes(id),
    program text,
    major text,
    cohort integer,
    academic_year integer,
    student_status text not null default 'active',
    preferred_language text not null default 'vi',
    advisor_name text,
    advisor_email text,
    ai_personalization_enabled boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint student_profiles_student_status_check check (
        student_status in ('active', 'inactive', 'leave', 'graduated', 'withdrawn')
    ),
    constraint student_profiles_preferred_language_check check (
        preferred_language in ('vi', 'en')
    )
);

create table if not exists courses (
    id uuid primary key default gen_random_uuid(),
    institute_id uuid references institutes(id),
    course_code text not null,
    course_title text not null,
    credits integer not null default 3,
    semester text,
    academic_year text,
    instructor text,
    is_active boolean not null default true,
    unique (course_code, semester, academic_year),
    constraint courses_credits_check check (credits > 0)
);

create table if not exists enrollments (
    id uuid primary key default gen_random_uuid(),
    student_profile_id uuid not null references student_profiles(id) on delete cascade,
    course_id uuid not null references courses(id) on delete cascade,
    status text not null default 'enrolled',
    created_at timestamptz not null default now(),
    unique (student_profile_id, course_id),
    constraint enrollments_status_check check (
        status in ('enrolled', 'completed', 'dropped', 'waitlisted')
    )
);

create table if not exists academic_summaries (
    id uuid primary key default gen_random_uuid(),
    student_profile_id uuid not null unique references student_profiles(id) on delete cascade,
    gpa numeric(3,2),
    credits_earned integer not null default 0,
    credits_required integer not null default 120,
    current_semester text,
    academic_status text not null default 'normal',
    updated_at timestamptz not null default now(),
    constraint academic_summaries_gpa_check check (gpa is null or (gpa >= 0 and gpa <= 4)),
    constraint academic_summaries_credits_earned_check check (credits_earned >= 0),
    constraint academic_summaries_credits_required_check check (credits_required > 0),
    constraint academic_summaries_academic_status_check check (
        academic_status in ('normal', 'warning', 'probation', 'suspended')
    )
);

create table if not exists schedules (
    id uuid primary key default gen_random_uuid(),
    student_profile_id uuid not null references student_profiles(id) on delete cascade,
    course_id uuid references courses(id) on delete set null,
    title text not null,
    schedule_type text not null,
    start_time timestamptz not null,
    end_time timestamptz not null,
    location text,
    building text,
    room text,
    instructor text,
    recurrence_rule text,
    constraint schedules_end_after_start_check check (end_time > start_time),
    constraint schedules_schedule_type_check check (
        schedule_type in ('class', 'lab', 'exam', 'office_hour', 'meeting', 'event', 'other')
    )
);

create table if not exists deadlines (
    id uuid primary key default gen_random_uuid(),
    student_profile_id uuid references student_profiles(id) on delete cascade,
    course_id uuid references courses(id) on delete set null,
    title text not null,
    kind text,
    due_at timestamptz not null,
    source_title text,
    source_url text
);

create table if not exists notifications (
    id uuid primary key default gen_random_uuid(),
    type text not null,
    title text not null,
    message text not null,
    priority text not null default 'medium',
    status text not null default 'draft',
    target_scope text not null default 'all',
    institute_id uuid references institutes(id) on delete set null,
    course_id uuid references courses(id) on delete set null,
    cohort integer,
    deadline timestamptz,
    event_date timestamptz,
    start_date timestamptz,
    end_date timestamptz,
    source_title text,
    source_url text,
    created_by uuid references users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint notifications_type_check check (
        type in ('announcement', 'deadline', 'event', 'academic', 'system', 'emergency')
    ),
    constraint notifications_priority_check check (priority in ('low', 'medium', 'high', 'urgent')),
    constraint notifications_status_check check (status in ('draft', 'published', 'archived')),
    constraint notifications_target_scope_check check (
        target_scope in ('all', 'institute', 'course', 'cohort', 'student')
    ),
    constraint notifications_date_range_check check (
        end_date is null or start_date is null or end_date >= start_date
    )
);

create table if not exists notification_reads (
    id uuid primary key default gen_random_uuid(),
    notification_id uuid not null references notifications(id) on delete cascade,
    user_id uuid not null references users(id) on delete cascade,
    read_at timestamptz not null default now(),
    important boolean not null default false,
    archived boolean not null default false,
    unique (notification_id, user_id)
);

create table if not exists events (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    description text,
    event_type text,
    location text,
    start_time timestamptz not null,
    end_time timestamptz,
    institute_id uuid references institutes(id) on delete set null,
    target_scope text not null default 'all',
    registration_required boolean not null default false,
    registration_deadline timestamptz,
    constraint events_target_scope_check check (
        target_scope in ('all', 'institute', 'course', 'cohort', 'student')
    ),
    constraint events_end_after_start_check check (end_time is null or end_time > start_time)
);

create table if not exists conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    title text not null default 'New conversation',
    title_manual boolean not null default false,
    topic text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    last_message_at timestamptz
);

create table if not exists messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references conversations(id) on delete cascade,
    role text not null,
    content text not null,
    answer_json jsonb,
    intent text,
    topic text,
    confidence numeric(4,3),
    needs_human_review boolean not null default false,
    created_at timestamptz not null default now(),
    constraint messages_role_check check (role in ('user', 'assistant', 'system', 'tool')),
    constraint messages_confidence_check check (
        confidence is null or (confidence >= 0 and confidence <= 1)
    )
);

create table if not exists tickets (
    id uuid primary key default gen_random_uuid(),
    student_profile_id uuid not null references student_profiles(id) on delete cascade,
    institute_id uuid references institutes(id) on delete set null,
    subject text not null,
    body text not null,
    department text,
    category text,
    priority text not null default 'medium',
    status text not null default 'submitted',
    confirmed_by_user boolean not null default true,
    created_by_ai boolean not null default false,
    include_chat_context boolean not null default false,
    included_context text,
    source_conversation_id uuid references conversations(id) on delete set null,
    origin_question text,
    assigned_admin_id uuid references users(id) on delete set null,
    submitted_at timestamptz,
    due_at timestamptz,
    sla_hours integer,
    resolution text,
    archived boolean not null default false,
    deleted boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint tickets_priority_check check (priority in ('low', 'medium', 'high', 'urgent')),
    constraint tickets_status_check check (
        status in ('submitted', 'open', 'in_progress', 'waiting_on_student', 'resolved', 'closed')
    ),
    constraint tickets_sla_hours_check check (sla_hours is null or sla_hours > 0)
);

create table if not exists ticket_messages (
    id uuid primary key default gen_random_uuid(),
    ticket_id uuid not null references tickets(id) on delete cascade,
    sender_user_id uuid references users(id) on delete set null,
    author_type text not null,
    body text not null,
    created_at timestamptz not null default now(),
    constraint ticket_messages_author_type_check check (
        author_type in ('student', 'admin', 'ai', 'system')
    )
);

create table if not exists ticket_status_history (
    id uuid primary key default gen_random_uuid(),
    ticket_id uuid not null references tickets(id) on delete cascade,
    old_status text,
    new_status text not null,
    changed_by uuid references users(id) on delete set null,
    changed_at timestamptz not null default now(),
    constraint ticket_status_history_old_status_check check (
        old_status is null
        or old_status in ('submitted', 'open', 'in_progress', 'waiting_on_student', 'resolved', 'closed')
    ),
    constraint ticket_status_history_new_status_check check (
        new_status in ('submitted', 'open', 'in_progress', 'waiting_on_student', 'resolved', 'closed')
    )
);

create table if not exists student_question_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete set null,
    conversation_id uuid references conversations(id) on delete set null,
    raw_question text,
    normalized_question text not null,
    intent text,
    topic text,
    institute_id uuid references institutes(id) on delete set null,
    course_id uuid references courses(id) on delete set null,
    created_at timestamptz not null default now(),
    is_anonymized boolean not null default true
);

create table if not exists question_trends (
    id uuid primary key default gen_random_uuid(),
    topic text not null,
    intent text,
    institute_id uuid references institutes(id) on delete set null,
    course_id uuid references courses(id) on delete set null,
    time_window text not null,
    frequency_count integer not null default 0,
    trend_score numeric(5,4) not null default 0,
    last_seen_at timestamptz,
    unique (topic, intent, institute_id, course_id, time_window),
    constraint question_trends_frequency_count_check check (frequency_count >= 0),
    constraint question_trends_trend_score_check check (trend_score >= 0)
);

create table if not exists suggested_questions (
    id uuid primary key default gen_random_uuid(),
    question_text text not null,
    source_type text not null,
    source_id uuid,
    notification_id uuid references notifications(id) on delete set null,
    topic text,
    intent text,
    category text,
    trigger_phase text,
    institute_id uuid references institutes(id) on delete set null,
    course_id uuid references courses(id) on delete set null,
    cohort integer,
    score numeric(6,3) not null default 0,
    priority integer not null default 0,
    created_by_ai boolean not null default false,
    approved_by_admin boolean not null default false,
    is_active boolean not null default true,
    valid_from timestamptz,
    valid_until timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint suggested_questions_source_type_check check (
        source_type in ('trend', 'notification', 'admin', 'ai', 'manual')
    ),
    constraint suggested_questions_valid_range_check check (
        valid_until is null or valid_from is null or valid_until >= valid_from
    )
);

create table if not exists audit_logs (
    id uuid primary key default gen_random_uuid(),
    actor_user_id uuid references users(id) on delete set null,
    action text not null,
    entity_type text not null,
    entity_id uuid,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_users_email on users(email);
create index if not exists idx_sessions_token_hash on sessions(token_hash);
create index if not exists idx_sessions_user_id on sessions(user_id);
create index if not exists idx_student_profiles_student_id on student_profiles(student_id);
create index if not exists idx_student_profiles_institute_id on student_profiles(institute_id);
create index if not exists idx_courses_institute_id on courses(institute_id);
create index if not exists idx_enrollments_student_profile_id on enrollments(student_profile_id);
create index if not exists idx_schedules_student_profile_id_start_time
    on schedules(student_profile_id, start_time);
create index if not exists idx_deadlines_student_profile_id_due_at
    on deadlines(student_profile_id, due_at);
create index if not exists idx_notifications_status_start_date_end_date
    on notifications(status, start_date, end_date);
create index if not exists idx_notifications_institute_id on notifications(institute_id);
create index if not exists idx_notification_reads_user_id on notification_reads(user_id);
create index if not exists idx_events_start_time on events(start_time);
create index if not exists idx_conversations_user_id_updated_at
    on conversations(user_id, updated_at desc);
create index if not exists idx_messages_conversation_id_created_at
    on messages(conversation_id, created_at);
create index if not exists idx_tickets_student_profile_id on tickets(student_profile_id);
create index if not exists idx_tickets_institute_id_status on tickets(institute_id, status);
create index if not exists idx_ticket_messages_ticket_id_created_at
    on ticket_messages(ticket_id, created_at);
create index if not exists idx_question_trends_topic on question_trends(topic);
create index if not exists idx_suggested_questions_is_active_priority
    on suggested_questions(is_active, priority desc);
create index if not exists idx_audit_logs_actor_user_id_created_at
    on audit_logs(actor_user_id, created_at desc);

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_users_updated_at on users;
create trigger set_users_updated_at
before update on users
for each row
execute function set_updated_at();

drop trigger if exists set_student_profiles_updated_at on student_profiles;
create trigger set_student_profiles_updated_at
before update on student_profiles
for each row
execute function set_updated_at();

drop trigger if exists set_notifications_updated_at on notifications;
create trigger set_notifications_updated_at
before update on notifications
for each row
execute function set_updated_at();

drop trigger if exists set_conversations_updated_at on conversations;
create trigger set_conversations_updated_at
before update on conversations
for each row
execute function set_updated_at();

drop trigger if exists set_tickets_updated_at on tickets;
create trigger set_tickets_updated_at
before update on tickets
for each row
execute function set_updated_at();

drop trigger if exists set_suggested_questions_updated_at on suggested_questions;
create trigger set_suggested_questions_updated_at
before update on suggested_questions
for each row
execute function set_updated_at();
