-- Canonical academic single-source transition.
--
-- Long-term direction:
--   - student_course_enrollments is the source of truth for registration,
--     transcript, GPA/CPA inputs, and earned credits.
--   - student_schedule_events is the source of truth for each student's calendar.
--   - class_meetings remains the section-level timetable template.
--   - Legacy portal tables that duplicated academic facts are dropped and not
--     recreated. Frontend must read through stable API responses, not DB tables.

create extension if not exists btree_gist;

drop table if exists schedules cascade;
drop table if exists enrollments cascade;
drop table if exists academic_summaries cascade;
drop function if exists app_stable_uuid(text);

alter table class_meetings
    add column if not exists start_time time,
    add column if not exists end_time time;

update class_meetings
set
    start_time = (start_at at time zone 'Asia/Ho_Chi_Minh')::time,
    end_time = (end_at at time zone 'Asia/Ho_Chi_Minh')::time
where start_time is null
   or end_time is null;

alter table class_meetings
    alter column start_time set not null,
    alter column end_time set not null;

alter table class_meetings
    drop constraint if exists class_meetings_local_time_order_check;

alter table class_meetings
    add constraint class_meetings_local_time_order_check
    check (
        ((start_at at time zone 'Asia/Ho_Chi_Minh')::date
            <> (end_at at time zone 'Asia/Ho_Chi_Minh')::date)
        or start_time < end_time
    );

create or replace function sync_class_meeting_local_times()
returns trigger
language plpgsql
as $$
begin
    new.start_time = (new.start_at at time zone 'Asia/Ho_Chi_Minh')::time;
    new.end_time = (new.end_at at time zone 'Asia/Ho_Chi_Minh')::time;
    return new;
end;
$$;

drop trigger if exists sync_class_meeting_local_times on class_meetings;
create trigger sync_class_meeting_local_times
before insert or update of start_at, end_at on class_meetings
for each row
execute function sync_class_meeting_local_times();

create table if not exists student_schedule_events (
    id uuid primary key default gen_random_uuid(),
    student_id uuid not null references student_profiles(id) on delete cascade,
    enrollment_id uuid references student_course_enrollments(id) on delete cascade,
    course_id uuid references courses(id) on delete set null,
    section_id uuid references course_sections(id) on delete set null,
    title text not null,
    meeting_type text not null,
    start_at timestamptz not null,
    end_at timestamptz not null,
    start_time time not null,
    end_time time not null,
    location text,
    building text,
    room text,
    instructor text,
    note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (student_id, enrollment_id, start_at, title),
    constraint student_schedule_events_meeting_type_check check (
        meeting_type in ('lecture', 'lab', 'tutorial', 'seminar', 'exam', 'office_hour', 'deadline')
    ),
    constraint student_schedule_events_end_after_start_check check (end_at > start_at),
    constraint student_schedule_events_local_time_order_check check (start_time < end_time)
);

create index if not exists idx_student_schedule_events_student_start
    on student_schedule_events(student_id, start_at);
create index if not exists idx_student_schedule_events_course_start
    on student_schedule_events(course_id, start_at);
create index if not exists idx_student_schedule_events_section_start
    on student_schedule_events(section_id, start_at);

alter table student_schedule_events
    drop constraint if exists student_schedule_events_no_overlap;

alter table student_schedule_events
    add constraint student_schedule_events_no_overlap
    exclude using gist (
        student_id with =,
        tstzrange(start_at, end_at, '[)') with &&
    )
    where (meeting_type in ('lecture', 'lab', 'tutorial', 'seminar', 'exam', 'office_hour'));

create or replace function sync_student_schedule_event_local_times()
returns trigger
language plpgsql
as $$
begin
    new.start_time = (new.start_at at time zone 'Asia/Ho_Chi_Minh')::time;
    new.end_time = (new.end_at at time zone 'Asia/Ho_Chi_Minh')::time;
    return new;
end;
$$;

drop trigger if exists sync_student_schedule_event_local_times on student_schedule_events;
create trigger sync_student_schedule_event_local_times
before insert or update of start_at, end_at on student_schedule_events
for each row
execute function sync_student_schedule_event_local_times();

drop trigger if exists set_student_schedule_events_updated_at on student_schedule_events;
create trigger set_student_schedule_events_updated_at
before update on student_schedule_events
for each row
execute function set_updated_at();
