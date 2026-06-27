-- Phase 13C addendum: denser June/July 2026 class schedule (mock demo data).
--
-- The timetable endpoint only shows meetings for sections a student is ENROLLED in, and the
-- Phase 13A seed gave each demo student only a few one-off summer sessions. This migration:
--   1. enrolls the primary demo students in a few more 2026-SUMMER sections (no grades), and
--   2. generates a recurring weekly timetable (Mon–Fri, plus Sat for PE) for every 2026-SUMMER
--      section across 2026-06-01..2026-07-31,
-- so each enrolled student sees roughly 2–5 class sessions per weekday.
--
-- Additive and idempotent (on conflict do update); the one-off lecture/exam/deadline rows from
-- migration 000007 are preserved. This is mock demo data, not an official VinUni timetable.

-- 1) Extra summer enrollments (status 'enrolled'/'retaking', no grades) to widen daily variety.
with enrollment_seed (
    id,
    student_email,
    course_code,
    term_code,
    section_code,
    status,
    attempt_no,
    is_improvement,
    retake_of_enrollment_id
) as (
    values
        ('13000000-13ae-4000-8000-000000000024'::uuid, 'student.cs.demo@vinuni.edu.vn', 'GEN102', '2026-SUMMER', 'GEN102-A', 'enrolled', 1, false, null::uuid),
        ('13000000-13ae-4000-8000-000000000025'::uuid, 'student.cs.demo@vinuni.edu.vn', 'CS201', '2026-SUMMER', 'CS201-A', 'enrolled', 1, false, null::uuid),
        ('13000000-13ae-4000-8000-000000000026'::uuid, 'student.cs02.demo@vinuni.edu.vn', 'GEN102', '2026-SUMMER', 'GEN102-A', 'enrolled', 1, false, null::uuid),
        ('13000000-13ae-4000-8000-000000000027'::uuid, 'student.cs02.demo@vinuni.edu.vn', 'PE101', '2026-SUMMER', 'PE101-A', 'enrolled', 1, false, null::uuid),
        ('13000000-13ae-4000-8000-000000000028'::uuid, 'student.business.demo@vinuni.edu.vn', 'GEN102', '2026-SUMMER', 'GEN102-A', 'enrolled', 1, false, null::uuid),
        ('13000000-13ae-4000-8000-000000000029'::uuid, 'student.business.demo@vinuni.edu.vn', 'PE101', '2026-SUMMER', 'PE101-A', 'enrolled', 1, false, null::uuid),
        ('13000000-13ae-4000-8000-000000000030'::uuid, 'student.business.demo@vinuni.edu.vn', 'BIO101', '2026-SUMMER', 'BIO101-A', 'enrolled', 1, false, null::uuid),
        ('13000000-13ae-4000-8000-000000000031'::uuid, 'student.health.demo@vinuni.edu.vn', 'GEN102', '2026-SUMMER', 'GEN102-A', 'enrolled', 1, false, null::uuid),
        ('13000000-13ae-4000-8000-000000000032'::uuid, 'student.health.demo@vinuni.edu.vn', 'MATH102', '2026-SUMMER', 'MATH102-A', 'enrolled', 1, false, null::uuid),
        ('13000000-13ae-4000-8000-000000000033'::uuid, 'student.liberal.demo@vinuni.edu.vn', 'GEN101', '2026-SUMMER', 'GEN101-A', 'retaking', 2, false, '13000000-13ae-4000-8000-000000000021'::uuid),
        ('13000000-13ae-4000-8000-000000000034'::uuid, 'student.liberal.demo@vinuni.edu.vn', 'HS101', '2026-SUMMER', 'HS101-A', 'enrolled', 1, false, null::uuid)
)
insert into student_course_enrollments (
    id,
    student_id,
    course_id,
    term_id,
    section_id,
    status,
    attempt_no,
    is_improvement,
    retake_of_enrollment_id,
    grade_10,
    grade_4,
    letter_grade,
    passed,
    earned_credits,
    is_gpa_counted,
    completed_at
)
select
    seed.id,
    sp.id,
    c.id,
    t.id,
    cs.id,
    seed.status,
    seed.attempt_no,
    seed.is_improvement,
    seed.retake_of_enrollment_id,
    null::numeric,
    null::numeric,
    null,
    false,
    0,
    false,
    null::timestamptz
from enrollment_seed seed
join users u on u.email = seed.student_email
join student_profiles sp on sp.user_id = u.id
join courses c
  on c.code = seed.course_code
 and c.semester = 'Summer 2026'
 and c.academic_year = '2026'
join academic_terms t on t.code = seed.term_code
join course_sections cs
  on cs.course_id = c.id
 and cs.term_id = t.id
 and cs.section_code = seed.section_code
on conflict (student_id, course_id, term_id, attempt_no) do update
set
    section_id = excluded.section_id,
    status = excluded.status,
    retake_of_enrollment_id = excluded.retake_of_enrollment_id;

-- 2) Recurring weekly timetable for every 2026-SUMMER section.
-- dow: 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat (Postgres extract(dow): Sun=0..Sat=6).
with slot (section_code, dow, start_time, dur_min, meeting_type, building, room_name) as (
    values
        -- General education
        ('GEN101-A', 1, time '08:00', 90, 'lecture', 'Academic Building A', 'A101'),
        ('GEN101-A', 3, time '10:00', 90, 'seminar', 'Academic Building A', 'A102'),
        ('GEN101-A', 5, time '08:00', 90, 'tutorial', 'Academic Building A', 'A101'),
        ('GEN102-A', 1, time '13:00', 90, 'lecture', 'Academic Building A', 'A101'),
        ('GEN102-A', 2, time '08:00', 90, 'lecture', 'Academic Building A', 'A101'),
        ('GEN102-A', 4, time '10:00', 90, 'seminar', 'Academic Building A', 'A102'),
        ('GEN102-A', 6, time '09:00', 90, 'lecture', 'Academic Building A', 'A101'),
        -- Mathematics
        ('MATH102-A', 1, time '10:00', 90, 'lecture', 'Academic Building A', 'A102'),
        ('MATH102-A', 3, time '10:00', 90, 'lecture', 'Academic Building A', 'A102'),
        ('MATH102-A', 5, time '10:00', 90, 'tutorial', 'Academic Building A', 'A102'),
        -- Computer science
        ('CS101-A', 1, time '13:00', 90, 'lecture', 'Academic Building A', 'A101'),
        ('CS101-A', 3, time '13:00', 120, 'lab', 'Computer Science Lab', 'CSL1'),
        ('CS101-A', 5, time '15:00', 60, 'office_hour', 'Faculty Office', 'FOH1'),
        ('CS102-A', 1, time '08:00', 90, 'lecture', 'Academic Building A', 'A101'),
        ('CS102-A', 3, time '13:00', 120, 'lab', 'Computer Science Lab', 'CSL1'),
        ('CS102-A', 4, time '13:00', 90, 'tutorial', 'Academic Building A', 'A101'),
        ('CS201-A', 2, time '13:00', 90, 'lecture', 'Academic Building A', 'A102'),
        ('CS201-A', 3, time '08:00', 90, 'lecture', 'Academic Building A', 'A102'),
        ('CS201-A', 4, time '10:45', 90, 'lecture', 'Academic Building A', 'A102'),
        ('CS201-A', 5, time '13:00', 90, 'tutorial', 'Academic Building A', 'A102'),
        ('CS301-A', 1, time '15:00', 90, 'lecture', 'Academic Building A', 'A101'),
        ('CS301-A', 4, time '15:00', 120, 'lab', 'Computer Science Lab', 'CSL1'),
        -- Business
        ('BUS101-A', 1, time '14:45', 90, 'lecture', 'Business School', 'B204'),
        ('BUS101-A', 3, time '14:45', 90, 'seminar', 'Business School', 'B204'),
        ('BUS201-A', 2, time '09:00', 90, 'seminar', 'Business School', 'B204'),
        ('BUS201-A', 4, time '09:00', 90, 'lecture', 'Business School', 'B204'),
        ('BUS201-A', 5, time '14:45', 90, 'seminar', 'Business School', 'B204'),
        -- Health sciences
        ('BIO101-A', 2, time '09:00', 120, 'lab', 'Health Sciences Lab', 'H201'),
        ('BIO101-A', 4, time '09:00', 90, 'lecture', 'Health Sciences Lab', 'H201'),
        ('HS101-A', 1, time '10:45', 90, 'lecture', 'Academic Building A', 'A102'),
        ('HS101-A', 3, time '10:45', 90, 'seminar', 'Academic Building A', 'A102'),
        ('HS101-A', 5, time '10:45', 90, 'lecture', 'Academic Building A', 'A102'),
        -- Physical education (includes a Saturday session)
        ('PE101-A', 2, time '16:00', 90, 'lab', 'Sports Complex', 'Gym 1'),
        ('PE101-A', 6, time '07:30', 90, 'lab', 'Sports Complex', 'Gym 1')
),
days as (
    select g::date as d
    from generate_series(date '2026-06-01', date '2026-07-31', interval '1 day') g
)
insert into class_meetings (
    section_id,
    title,
    meeting_type,
    start_at,
    end_at,
    room_id,
    note
)
select
    cs.id,
    coalesce(c.code, c.course_code)
        || ' ' || initcap(replace(slot.meeting_type, '_', ' '))
        || ' · ' || to_char(days.d, 'Dy') as title,
    slot.meeting_type,
    (days.d + slot.start_time) at time zone 'Asia/Ho_Chi_Minh' as start_at,
    (days.d + slot.start_time + make_interval(mins => slot.dur_min)) at time zone 'Asia/Ho_Chi_Minh' as end_at,
    r.id,
    'Weekly summer session (mock demo data).'
from slot
join days on extract(dow from days.d) = slot.dow
join course_sections cs on cs.section_code = slot.section_code
join academic_terms t on t.id = cs.term_id and t.code = '2026-SUMMER'
join courses c on c.id = cs.course_id
left join rooms r on r.building = slot.building and r.room_name = slot.room_name
on conflict (section_id, title, start_at) do update
set
    meeting_type = excluded.meeting_type,
    end_at = excluded.end_at,
    room_id = excluded.room_id,
    note = excluded.note;
