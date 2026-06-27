-- Phase 13A: Academic demo database core.
-- This is mock academic data for development/demo use; it is not an official VinUni curriculum.

create table if not exists faculties (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists programs (
    id uuid primary key default gen_random_uuid(),
    faculty_id uuid not null references faculties(id) on delete restrict,
    code text not null,
    name text not null,
    degree_level text not null,
    curriculum_year integer not null,
    total_required_credits integer not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (code, curriculum_year),
    constraint programs_curriculum_year_check check (curriculum_year >= 2000),
    constraint programs_total_required_credits_check check (total_required_credits >= 0)
);

create table if not exists academic_terms (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null,
    start_date date not null,
    end_date date not null,
    academic_year integer not null,
    term_order integer not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint academic_terms_date_range_check check (end_date >= start_date),
    constraint academic_terms_order_check check (term_order > 0)
);

alter table student_profiles add column if not exists student_code text;
alter table student_profiles add column if not exists full_name text;
alter table student_profiles add column if not exists faculty_id uuid;
alter table student_profiles add column if not exists program_id uuid;
alter table student_profiles add column if not exists cohort_year integer;
alter table student_profiles add column if not exists current_year integer;
alter table student_profiles add column if not exists status text;

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'student_profiles'::regclass
          and conname = 'student_profiles_faculty_id_fkey'
    ) then
        alter table student_profiles
            add constraint student_profiles_faculty_id_fkey
            foreign key (faculty_id) references faculties(id) on delete set null;
    end if;

    if not exists (
        select 1 from pg_constraint
        where conrelid = 'student_profiles'::regclass
          and conname = 'student_profiles_program_id_fkey'
    ) then
        alter table student_profiles
            add constraint student_profiles_program_id_fkey
            foreign key (program_id) references programs(id) on delete set null;
    end if;

    if not exists (
        select 1 from pg_constraint
        where conrelid = 'student_profiles'::regclass
          and conname = 'student_profiles_academic_status_check'
    ) then
        alter table student_profiles
            add constraint student_profiles_academic_status_check
            check (
                status is null
                or status in ('active', 'inactive', 'leave', 'graduated', 'withdrawn', 'suspended')
            ) not valid;
    end if;
end $$;

update student_profiles sp
set
    student_code = coalesce(sp.student_code, sp.student_id),
    full_name = coalesce(sp.full_name, u.full_name),
    cohort_year = coalesce(sp.cohort_year, sp.cohort),
    current_year = coalesce(sp.current_year, sp.academic_year),
    status = coalesce(sp.status, sp.student_status)
from users u
where u.id = sp.user_id;

alter table courses drop constraint if exists courses_credits_check;
alter table courses add column if not exists code text;
alter table courses add column if not exists name text;
alter table courses add column if not exists course_level integer;
alter table courses add column if not exists department_code text;
alter table courses add column if not exists is_general_education boolean not null default false;
alter table courses add column if not exists description text;

update courses
set
    code = coalesce(code, course_code),
    name = coalesce(name, course_title),
    course_level = coalesce(
        course_level,
        nullif(substring(course_code from '[0-9]+'), '')::integer
    ),
    department_code = coalesce(
        department_code,
        nullif(regexp_replace(course_code, '[0-9].*$', ''), '')
    )
where code is null
   or name is null
   or course_level is null
   or department_code is null;

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'courses'::regclass
          and conname = 'courses_supported_credits_check'
    ) then
        alter table courses
            add constraint courses_supported_credits_check
            check (credits in (0, 2, 3, 4)) not valid;
    end if;
end $$;

create table if not exists curriculum_courses (
    id uuid primary key default gen_random_uuid(),
    program_id uuid not null references programs(id) on delete cascade,
    course_id uuid not null references courses(id) on delete cascade,
    category text not null,
    is_required boolean not null default true,
    suggested_year integer,
    suggested_term integer,
    min_required_grade_4 numeric(3,2),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (program_id, course_id, category),
    constraint curriculum_courses_category_check check (
        category in (
            'general_education',
            'foundation',
            'major_core',
            'major_elective',
            'physical_education',
            'capstone'
        )
    ),
    constraint curriculum_courses_suggested_year_check check (
        suggested_year is null or suggested_year between 1 and 6
    ),
    constraint curriculum_courses_suggested_term_check check (
        suggested_term is null or suggested_term between 1 and 4
    ),
    constraint curriculum_courses_min_grade_check check (
        min_required_grade_4 is null
        or (min_required_grade_4 >= 0 and min_required_grade_4 <= 4)
    )
);

create table if not exists course_requisites (
    id uuid primary key default gen_random_uuid(),
    course_id uuid not null references courses(id) on delete cascade,
    required_course_id uuid not null references courses(id) on delete cascade,
    requisite_type text not null,
    min_grade_4 numeric(3,2),
    note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (course_id, required_course_id, requisite_type),
    constraint course_requisites_type_check check (requisite_type in ('prerequisite', 'corequisite')),
    constraint course_requisites_min_grade_check check (
        min_grade_4 is null or (min_grade_4 >= 0 and min_grade_4 <= 4)
    ),
    constraint course_requisites_not_self_check check (course_id <> required_course_id)
);

create table if not exists rooms (
    id uuid primary key default gen_random_uuid(),
    building text not null,
    room_name text not null,
    capacity integer not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (building, room_name),
    constraint rooms_capacity_check check (capacity >= 0)
);

create table if not exists course_sections (
    id uuid primary key default gen_random_uuid(),
    course_id uuid not null references courses(id) on delete cascade,
    term_id uuid not null references academic_terms(id) on delete cascade,
    section_code text not null,
    instructor_name text,
    capacity integer not null,
    status text not null default 'open',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (course_id, term_id, section_code),
    constraint course_sections_capacity_check check (capacity >= 0),
    constraint course_sections_status_check check (status in ('planned', 'open', 'closed', 'cancelled'))
);

create table if not exists student_course_enrollments (
    id uuid primary key default gen_random_uuid(),
    student_id uuid not null references student_profiles(id) on delete cascade,
    course_id uuid not null references courses(id) on delete restrict,
    term_id uuid not null references academic_terms(id) on delete restrict,
    section_id uuid references course_sections(id) on delete set null,
    status text not null,
    attempt_no integer not null default 1,
    is_improvement boolean not null default false,
    retake_of_enrollment_id uuid
        references student_course_enrollments(id) on delete set null
        deferrable initially deferred,
    grade_10 numeric(4,2),
    grade_4 numeric(3,2),
    letter_grade text,
    passed boolean not null default false,
    earned_credits integer not null default 0,
    is_gpa_counted boolean not null default false,
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (student_id, course_id, term_id, attempt_no),
    constraint student_course_enrollments_status_check check (
        status in (
            'planned',
            'enrolled',
            'completed',
            'failed',
            'withdrawn',
            'retaking',
            'improvement'
        )
    ),
    constraint student_course_enrollments_attempt_check check (attempt_no > 0),
    constraint student_course_enrollments_grade_10_check check (
        grade_10 is null or (grade_10 >= 0 and grade_10 <= 10)
    ),
    constraint student_course_enrollments_grade_4_check check (
        grade_4 is null or (grade_4 >= 0 and grade_4 <= 4)
    ),
    constraint student_course_enrollments_earned_credits_check check (earned_credits >= 0),
    constraint student_course_enrollments_completed_status_check check (
        completed_at is null
        or status in ('completed', 'failed', 'withdrawn', 'improvement')
    )
);

create unique index if not exists idx_student_course_enrollments_one_cpa_attempt
    on student_course_enrollments(student_id, course_id)
    where is_gpa_counted = true;

create table if not exists class_meetings (
    id uuid primary key default gen_random_uuid(),
    section_id uuid not null references course_sections(id) on delete cascade,
    title text not null,
    meeting_type text not null,
    start_at timestamptz not null,
    end_at timestamptz not null,
    room_id uuid references rooms(id) on delete set null,
    note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (section_id, title, start_at),
    constraint class_meetings_type_check check (
        meeting_type in ('lecture', 'lab', 'tutorial', 'seminar', 'exam', 'office_hour', 'deadline')
    ),
    constraint class_meetings_end_after_start_check check (end_at > start_at)
);

create index if not exists idx_student_profiles_student_code on student_profiles(student_code);
create index if not exists idx_student_profiles_faculty_id on student_profiles(faculty_id);
create index if not exists idx_student_profiles_program_id on student_profiles(program_id);
create index if not exists idx_courses_code on courses(code);
create index if not exists idx_courses_department_code on courses(department_code);
create index if not exists idx_programs_faculty_id on programs(faculty_id);
create index if not exists idx_curriculum_courses_program_category
    on curriculum_courses(program_id, category, suggested_year, suggested_term);
create index if not exists idx_course_requisites_course_id on course_requisites(course_id);
create index if not exists idx_student_course_enrollments_student_term
    on student_course_enrollments(student_id, term_id);
create index if not exists idx_student_course_enrollments_course_term
    on student_course_enrollments(course_id, term_id);
create index if not exists idx_course_sections_term_id on course_sections(term_id);
create index if not exists idx_class_meetings_section_start
    on class_meetings(section_id, start_at);

create or replace function normalize_student_course_enrollment()
returns trigger
language plpgsql
as $$
declare
    course_credits integer;
begin
    select credits into course_credits
    from courses
    where id = new.course_id;

    if course_credits is null then
        return new;
    end if;

    if new.grade_10 is not null or new.grade_4 is not null then
        if coalesce(new.grade_10, 0) < 4.0 or coalesce(new.grade_4, 0) < 1.0 then
            new.letter_grade = 'F';
            new.passed = false;
            new.earned_credits = 0;
        elsif new.status in ('completed', 'improvement') then
            new.passed = true;
            if course_credits > 0 and new.earned_credits = 0 then
                new.earned_credits = course_credits;
            end if;
        end if;
    end if;

    if course_credits = 0 then
        new.earned_credits = 0;
        new.is_gpa_counted = false;
    end if;

    if new.status = 'failed' then
        new.passed = false;
        new.earned_credits = 0;
    end if;

    return new;
end;
$$;

drop trigger if exists normalize_student_course_enrollment on student_course_enrollments;
create trigger normalize_student_course_enrollment
before insert or update on student_course_enrollments
for each row
execute function normalize_student_course_enrollment();

drop trigger if exists set_faculties_updated_at on faculties;
create trigger set_faculties_updated_at
before update on faculties
for each row
execute function set_updated_at();

drop trigger if exists set_programs_updated_at on programs;
create trigger set_programs_updated_at
before update on programs
for each row
execute function set_updated_at();

drop trigger if exists set_academic_terms_updated_at on academic_terms;
create trigger set_academic_terms_updated_at
before update on academic_terms
for each row
execute function set_updated_at();

drop trigger if exists set_curriculum_courses_updated_at on curriculum_courses;
create trigger set_curriculum_courses_updated_at
before update on curriculum_courses
for each row
execute function set_updated_at();

drop trigger if exists set_course_requisites_updated_at on course_requisites;
create trigger set_course_requisites_updated_at
before update on course_requisites
for each row
execute function set_updated_at();

drop trigger if exists set_rooms_updated_at on rooms;
create trigger set_rooms_updated_at
before update on rooms
for each row
execute function set_updated_at();

drop trigger if exists set_course_sections_updated_at on course_sections;
create trigger set_course_sections_updated_at
before update on course_sections
for each row
execute function set_updated_at();

drop trigger if exists set_student_course_enrollments_updated_at on student_course_enrollments;
create trigger set_student_course_enrollments_updated_at
before update on student_course_enrollments
for each row
execute function set_updated_at();

drop trigger if exists set_class_meetings_updated_at on class_meetings;
create trigger set_class_meetings_updated_at
before update on class_meetings
for each row
execute function set_updated_at();

insert into faculties (code, name)
values
    ('CECS', 'Computer Science'),
    ('VIB', 'Business Administration'),
    ('CHS', 'Health Sciences'),
    ('GEN', 'General Education')
on conflict (code) do update
set name = excluded.name;

insert into programs (
    faculty_id, code, name, degree_level, curriculum_year, total_required_credits
)
values
    (
        (select id from faculties where code = 'CECS'),
        'BS-CS',
        'Computer Science',
        'bachelor',
        2026,
        120
    ),
    (
        (select id from faculties where code = 'VIB'),
        'BBA',
        'Business Administration',
        'bachelor',
        2026,
        120
    ),
    (
        (select id from faculties where code = 'CHS'),
        'BHS',
        'Health Sciences',
        'bachelor',
        2026,
        120
    ),
    (
        (select id from faculties where code = 'GEN'),
        'GEN-FOUNDATION',
        'General Education Foundation',
        'foundation',
        2026,
        24
    )
on conflict (code, curriculum_year) do update
set
    faculty_id = excluded.faculty_id,
    name = excluded.name,
    degree_level = excluded.degree_level,
    total_required_credits = excluded.total_required_credits;

insert into academic_terms (code, name, start_date, end_date, academic_year, term_order)
values
    ('2025-FALL', 'Fall Term 2025', date '2025-09-01', date '2025-12-20', 2025, 1),
    ('2026-SPRING', 'Spring Term 2026', date '2026-01-12', date '2026-05-15', 2026, 2),
    ('2026-SUMMER', 'Summer Term 2026', date '2026-06-01', date '2026-07-31', 2026, 3)
on conflict (code) do update
set
    name = excluded.name,
    start_date = excluded.start_date,
    end_date = excluded.end_date,
    academic_year = excluded.academic_year,
    term_order = excluded.term_order;

with course_seed (
    code,
    name,
    credits,
    course_level,
    department_code,
    is_general_education,
    description,
    institute_code
) as (
    values
        ('GEN101', 'Academic English', 2, 101, 'GEN', true, 'Mock demo course for academic English practice.', 'CASE'),
        ('GEN102', 'Critical Thinking', 2, 102, 'GEN', true, 'Mock demo course for analytical reasoning and argument.', 'CASE'),
        ('MATH101', 'Calculus I', 3, 101, 'MATH', false, 'Mock demo course covering introductory calculus.', 'CECS'),
        ('MATH102', 'Discrete Mathematics', 3, 102, 'MATH', false, 'Mock demo course covering discrete structures.', 'CECS'),
        ('CS101', 'Introduction to Programming', 3, 101, 'CS', false, 'Mock demo course covering programming fundamentals.', 'CECS'),
        ('CS102', 'Data Structures', 4, 102, 'CS', false, 'Mock demo course covering data structures.', 'CECS'),
        ('CS201', 'Algorithms', 4, 201, 'CS', false, 'Mock demo course covering algorithm design and analysis.', 'CECS'),
        ('CS301', 'Database Systems', 4, 301, 'CS', false, 'Mock demo course covering relational database systems.', 'CECS'),
        ('BUS101', 'Principles of Management', 3, 101, 'BUS', false, 'Mock demo course covering management foundations.', 'VIB'),
        ('BUS201', 'Marketing Fundamentals', 3, 201, 'BUS', false, 'Mock demo course covering marketing concepts.', 'VIB'),
        ('ECON101', 'Microeconomics', 3, 101, 'ECON', false, 'Mock demo course covering microeconomic principles.', 'VIB'),
        ('BIO101', 'Human Biology', 3, 101, 'BIO', false, 'Mock demo course covering human biology basics.', 'CHS'),
        ('HS101', 'Public Health', 3, 101, 'HS', false, 'Mock demo course covering public health foundations.', 'CHS'),
        ('PE101', 'Physical Education', 0, 101, 'PE', true, 'Mock demo zero-credit physical education course.', 'CASE'),
        ('CAP401', 'Capstone Project', 4, 401, 'CAP', false, 'Mock demo capstone project course.', 'CECS')
)
insert into courses (
    institute_id,
    course_code,
    course_title,
    credits,
    semester,
    academic_year,
    instructor,
    is_active,
    code,
    name,
    course_level,
    department_code,
    is_general_education,
    description
)
select
    i.id,
    seed.code,
    seed.name,
    seed.credits,
    'Summer 2026',
    '2026',
    null,
    true,
    seed.code,
    seed.name,
    seed.course_level,
    seed.department_code,
    seed.is_general_education,
    seed.description
from course_seed seed
left join institutes i on i.code = seed.institute_code
on conflict (course_code, semester, academic_year) do update
set
    institute_id = excluded.institute_id,
    course_title = excluded.course_title,
    credits = excluded.credits,
    instructor = excluded.instructor,
    is_active = true,
    code = excluded.code,
    name = excluded.name,
    course_level = excluded.course_level,
    department_code = excluded.department_code,
    is_general_education = excluded.is_general_education,
    description = excluded.description;

with curriculum_seed (
    program_code,
    course_code,
    category,
    is_required,
    suggested_year,
    suggested_term,
    min_required_grade_4
) as (
    values
        ('BS-CS', 'GEN101', 'general_education', true, 1, 1, 1.00),
        ('BS-CS', 'GEN102', 'general_education', true, 1, 2, 1.00),
        ('BS-CS', 'PE101', 'physical_education', true, 1, 3, null::numeric),
        ('BS-CS', 'MATH101', 'foundation', true, 1, 1, 1.00),
        ('BS-CS', 'MATH102', 'foundation', true, 1, 3, 1.00),
        ('BS-CS', 'CS101', 'major_core', true, 1, 1, 1.00),
        ('BS-CS', 'CS102', 'major_core', true, 1, 2, 1.00),
        ('BS-CS', 'CS201', 'major_core', true, 2, 1, 1.00),
        ('BS-CS', 'CS301', 'major_core', true, 3, 1, 1.00),
        ('BS-CS', 'CAP401', 'capstone', true, 4, 2, 1.00),
        ('BBA', 'GEN101', 'general_education', true, 1, 1, 1.00),
        ('BBA', 'GEN102', 'general_education', true, 1, 2, 1.00),
        ('BBA', 'PE101', 'physical_education', true, 1, 3, null::numeric),
        ('BBA', 'MATH101', 'foundation', true, 1, 1, 1.00),
        ('BBA', 'BUS101', 'major_core', true, 1, 1, 1.00),
        ('BBA', 'ECON101', 'foundation', true, 1, 2, 1.00),
        ('BBA', 'BUS201', 'major_core', true, 2, 1, 1.00),
        ('BBA', 'CS301', 'major_elective', false, 3, 2, 1.00),
        ('BHS', 'GEN101', 'general_education', true, 1, 1, 1.00),
        ('BHS', 'GEN102', 'general_education', true, 1, 2, 1.00),
        ('BHS', 'PE101', 'physical_education', true, 1, 3, null::numeric),
        ('BHS', 'BIO101', 'foundation', true, 1, 1, 1.00),
        ('BHS', 'HS101', 'major_core', true, 1, 2, 1.00),
        ('BHS', 'ECON101', 'major_elective', false, 2, 2, 1.00),
        ('GEN-FOUNDATION', 'GEN101', 'general_education', true, 1, 1, 1.00),
        ('GEN-FOUNDATION', 'GEN102', 'general_education', true, 1, 2, 1.00),
        ('GEN-FOUNDATION', 'PE101', 'physical_education', true, 1, 3, null::numeric),
        ('GEN-FOUNDATION', 'MATH101', 'foundation', false, 1, 2, 1.00),
        ('GEN-FOUNDATION', 'BIO101', 'foundation', false, 1, 2, 1.00),
        ('GEN-FOUNDATION', 'ECON101', 'major_elective', false, 1, 3, 1.00)
)
insert into curriculum_courses (
    program_id,
    course_id,
    category,
    is_required,
    suggested_year,
    suggested_term,
    min_required_grade_4
)
select
    p.id,
    c.id,
    seed.category,
    seed.is_required,
    seed.suggested_year,
    seed.suggested_term,
    seed.min_required_grade_4
from curriculum_seed seed
join programs p on p.code = seed.program_code and p.curriculum_year = 2026
join courses c
  on c.code = seed.course_code
 and c.semester = 'Summer 2026'
 and c.academic_year = '2026'
on conflict (program_id, course_id, category) do update
set
    is_required = excluded.is_required,
    suggested_year = excluded.suggested_year,
    suggested_term = excluded.suggested_term,
    min_required_grade_4 = excluded.min_required_grade_4;

with requisite_seed (course_code, required_course_code, requisite_type, min_grade_4, note) as (
    values
        ('CS102', 'CS101', 'prerequisite', 1.00, 'Mock demo prerequisite.'),
        ('CS201', 'CS102', 'prerequisite', 1.00, 'Mock demo prerequisite.'),
        ('CS201', 'MATH102', 'corequisite', 1.00, 'Mock demo corequisite.'),
        ('CS301', 'CS102', 'prerequisite', 1.00, 'Mock demo prerequisite.'),
        ('CAP401', 'CS201', 'prerequisite', 1.00, 'Mock demo prerequisite.')
)
insert into course_requisites (
    course_id,
    required_course_id,
    requisite_type,
    min_grade_4,
    note
)
select
    course.id,
    required_course.id,
    seed.requisite_type,
    seed.min_grade_4,
    seed.note
from requisite_seed seed
join courses course
  on course.code = seed.course_code
 and course.semester = 'Summer 2026'
 and course.academic_year = '2026'
join courses required_course
  on required_course.code = seed.required_course_code
 and required_course.semester = 'Summer 2026'
 and required_course.academic_year = '2026'
on conflict (course_id, required_course_id, requisite_type) do update
set
    min_grade_4 = excluded.min_grade_4,
    note = excluded.note;

insert into users (id, email, password_hash, full_name, preferred_name, status)
values
    (
        '13000000-13a0-4000-8000-000000000001',
        'student.cs.demo@vinuni.edu.vn',
        null,
        'Demo Computer Science Student',
        'CS Demo',
        'active'
    ),
    (
        '13000000-13a0-4000-8000-000000000002',
        'student.cs02.demo@vinuni.edu.vn',
        null,
        'Demo Computer Science Second Student',
        'CS Demo 02',
        'active'
    ),
    (
        '13000000-13a0-4000-8000-000000000003',
        'student.business.demo@vinuni.edu.vn',
        null,
        'Demo Business Student',
        'Business Demo',
        'active'
    ),
    (
        '13000000-13a0-4000-8000-000000000004',
        'student.health.demo@vinuni.edu.vn',
        null,
        'Demo Health Sciences Student',
        'Health Demo',
        'active'
    ),
    (
        '13000000-13a0-4000-8000-000000000005',
        'student.liberal.demo@vinuni.edu.vn',
        null,
        'Demo General Education Student',
        'General Demo',
        'active'
    )
on conflict (email) do update
set
    preferred_name = coalesce(users.preferred_name, excluded.preferred_name),
    updated_at = now();

insert into user_roles (user_id, role_id)
select u.id, r.id
from users u
cross join roles r
where u.email in (
        'student.cs.demo@vinuni.edu.vn',
        'student.cs02.demo@vinuni.edu.vn',
        'student.business.demo@vinuni.edu.vn',
        'student.health.demo@vinuni.edu.vn',
        'student.liberal.demo@vinuni.edu.vn'
    )
  and r.code = 'student'
on conflict (user_id, role_id) do nothing;

with student_seed (
    id,
    email,
    student_code,
    institute_code,
    faculty_code,
    program_code,
    major,
    cohort_year,
    current_year,
    advisor_name,
    advisor_email
) as (
    values
        (
            '13000000-13a1-4000-8000-000000000001'::uuid,
            'student.cs.demo@vinuni.edu.vn',
            'D13CECS001',
            'CECS',
            'CECS',
            'BS-CS',
            'Computer Science',
            2025,
            2,
            'Demo CS Advisor',
            'advisor.cs.demo@vinuni.edu.vn'
        ),
        (
            '13000000-13a1-4000-8000-000000000002'::uuid,
            'student.cs02.demo@vinuni.edu.vn',
            'D13CECS002',
            'CECS',
            'CECS',
            'BS-CS',
            'Computer Science',
            2024,
            3,
            'Demo CS Advisor',
            'advisor.cs.demo@vinuni.edu.vn'
        ),
        (
            '13000000-13a1-4000-8000-000000000003'::uuid,
            'student.business.demo@vinuni.edu.vn',
            'D13VIB001',
            'VIB',
            'VIB',
            'BBA',
            'Business Administration',
            2025,
            2,
            'Demo Business Advisor',
            'advisor.business.demo@vinuni.edu.vn'
        ),
        (
            '13000000-13a1-4000-8000-000000000004'::uuid,
            'student.health.demo@vinuni.edu.vn',
            'D13CHS001',
            'CHS',
            'CHS',
            'BHS',
            'Health Sciences',
            2026,
            1,
            'Demo Health Advisor',
            'advisor.health.demo@vinuni.edu.vn'
        ),
        (
            '13000000-13a1-4000-8000-000000000005'::uuid,
            'student.liberal.demo@vinuni.edu.vn',
            'D13GEN001',
            'CASE',
            'GEN',
            'GEN-FOUNDATION',
            'General Education',
            2026,
            1,
            'Demo General Education Advisor',
            'advisor.general.demo@vinuni.edu.vn'
        )
)
insert into student_profiles (
    id,
    user_id,
    student_id,
    institute_id,
    program,
    major,
    cohort,
    academic_year,
    student_status,
    preferred_language,
    advisor_name,
    advisor_email,
    ai_personalization_enabled,
    student_code,
    full_name,
    faculty_id,
    program_id,
    cohort_year,
    current_year,
    status
)
select
    seed.id,
    u.id,
    seed.student_code,
    i.id,
    p.name,
    seed.major,
    seed.cohort_year,
    seed.current_year,
    'active',
    'en',
    seed.advisor_name,
    seed.advisor_email,
    true,
    seed.student_code,
    u.full_name,
    f.id,
    p.id,
    seed.cohort_year,
    seed.current_year,
    'active'
from student_seed seed
join users u on u.email = seed.email
join institutes i on i.code = seed.institute_code
join faculties f on f.code = seed.faculty_code
join programs p on p.code = seed.program_code and p.curriculum_year = 2026
on conflict (user_id) do update
set
    student_code = coalesce(student_profiles.student_code, student_profiles.student_id, excluded.student_code),
    full_name = coalesce(student_profiles.full_name, excluded.full_name),
    faculty_id = excluded.faculty_id,
    program_id = excluded.program_id,
    cohort_year = coalesce(student_profiles.cohort_year, student_profiles.cohort, excluded.cohort_year),
    current_year = coalesce(student_profiles.current_year, student_profiles.academic_year, excluded.current_year),
    status = coalesce(student_profiles.status, student_profiles.student_status, excluded.status),
    updated_at = now();

with summary_seed (student_email, gpa, credits_earned, credits_required, current_semester, academic_status) as (
    values
        ('student.cs.demo@vinuni.edu.vn', 3.10::numeric, 8, 120, 'Summer 2026', 'normal'),
        ('student.cs02.demo@vinuni.edu.vn', 3.38::numeric, 10, 120, 'Summer 2026', 'normal'),
        ('student.business.demo@vinuni.edu.vn', 2.70::numeric, 8, 120, 'Summer 2026', 'warning'),
        ('student.health.demo@vinuni.edu.vn', 3.35::numeric, 5, 120, 'Summer 2026', 'normal'),
        ('student.liberal.demo@vinuni.edu.vn', 2.65::numeric, 2, 24, 'Summer 2026', 'normal')
)
insert into academic_summaries (
    student_profile_id,
    gpa,
    credits_earned,
    credits_required,
    current_semester,
    academic_status,
    updated_at
)
select
    sp.id,
    seed.gpa,
    seed.credits_earned,
    seed.credits_required,
    seed.current_semester,
    seed.academic_status,
    now()
from summary_seed seed
join users u on u.email = seed.student_email
join student_profiles sp on sp.user_id = u.id
on conflict (student_profile_id) do update
set
    gpa = excluded.gpa,
    credits_earned = excluded.credits_earned,
    credits_required = excluded.credits_required,
    current_semester = excluded.current_semester,
    academic_status = excluded.academic_status,
    updated_at = now();

insert into rooms (building, room_name, capacity)
values
    ('Academic Building A', 'A101', 42),
    ('Academic Building A', 'A102', 48),
    ('Computer Science Lab', 'CSL1', 30),
    ('Business School', 'B204', 50),
    ('Health Sciences Lab', 'H201', 24),
    ('Sports Complex', 'Gym 1', 35),
    ('Faculty Office', 'FOH1', 12)
on conflict (building, room_name) do update
set capacity = excluded.capacity;

with section_seed (course_code, section_code, instructor_name, capacity, status) as (
    values
        ('GEN101', 'GEN101-A', 'Demo English Instructor', 36, 'open'),
        ('GEN102', 'GEN102-A', 'Demo Critical Thinking Instructor', 36, 'open'),
        ('MATH102', 'MATH102-A', 'Demo Mathematics Instructor', 40, 'open'),
        ('CS101', 'CS101-A', 'Demo Programming Instructor', 32, 'open'),
        ('CS102', 'CS102-A', 'Demo Data Structures Instructor', 30, 'open'),
        ('CS201', 'CS201-A', 'Demo Algorithms Instructor', 30, 'open'),
        ('CS301', 'CS301-A', 'Demo Database Instructor', 30, 'open'),
        ('BUS101', 'BUS101-A', 'Demo Management Instructor', 45, 'open'),
        ('BUS201', 'BUS201-A', 'Demo Marketing Instructor', 45, 'open'),
        ('BIO101', 'BIO101-A', 'Demo Biology Instructor', 28, 'open'),
        ('HS101', 'HS101-A', 'Demo Public Health Instructor', 28, 'open'),
        ('PE101', 'PE101-A', 'Demo PE Instructor', 35, 'open'),
        ('CAP401', 'CAP401-A', 'Demo Capstone Advisor', 20, 'planned')
)
insert into course_sections (
    course_id,
    term_id,
    section_code,
    instructor_name,
    capacity,
    status
)
select
    c.id,
    t.id,
    seed.section_code,
    seed.instructor_name,
    seed.capacity,
    seed.status
from section_seed seed
join courses c
  on c.code = seed.course_code
 and c.semester = 'Summer 2026'
 and c.academic_year = '2026'
join academic_terms t on t.code = '2026-SUMMER'
on conflict (course_id, term_id, section_code) do update
set
    instructor_name = excluded.instructor_name,
    capacity = excluded.capacity,
    status = excluded.status;

with enrollment_seed (
    id,
    student_email,
    course_code,
    term_code,
    section_code,
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
) as (
    values
        ('13000000-13ae-4000-8000-000000000001'::uuid, 'student.cs.demo@vinuni.edu.vn', 'GEN101', '2025-FALL', null, 'completed', 1, false, null::uuid, 8.00::numeric, 3.30::numeric, 'B+', true, 2, true, '2025-12-20 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000002'::uuid, 'student.cs.demo@vinuni.edu.vn', 'CS101', '2026-SPRING', null, 'completed', 1, false, null::uuid, 7.50::numeric, 3.00::numeric, 'B', true, 3, true, '2026-05-12 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000003'::uuid, 'student.cs.demo@vinuni.edu.vn', 'CS102', '2026-SPRING', null, 'failed', 1, false, null::uuid, 3.50::numeric, 0.00::numeric, 'F', false, 0, false, '2026-05-12 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000004'::uuid, 'student.cs.demo@vinuni.edu.vn', 'CS102', '2026-SUMMER', 'CS102-A', 'retaking', 2, false, '13000000-13ae-4000-8000-000000000003'::uuid, null::numeric, null::numeric, null, false, 0, false, null::timestamptz),
        ('13000000-13ae-4000-8000-000000000005'::uuid, 'student.cs.demo@vinuni.edu.vn', 'MATH102', '2026-SUMMER', 'MATH102-A', 'enrolled', 1, false, null::uuid, null::numeric, null::numeric, null, false, 0, false, null::timestamptz),
        ('13000000-13ae-4000-8000-000000000006'::uuid, 'student.cs.demo@vinuni.edu.vn', 'PE101', '2026-SUMMER', 'PE101-A', 'completed', 1, false, null::uuid, null::numeric, null::numeric, 'P', true, 0, false, '2026-07-10 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000007'::uuid, 'student.cs02.demo@vinuni.edu.vn', 'CS101', '2025-FALL', null, 'completed', 1, false, null::uuid, 6.00::numeric, 2.00::numeric, 'C', true, 3, false, '2025-12-20 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000008'::uuid, 'student.cs02.demo@vinuni.edu.vn', 'CS101', '2026-SPRING', null, 'improvement', 2, true, '13000000-13ae-4000-8000-000000000007'::uuid, 8.80::numeric, 3.70::numeric, 'A-', true, 3, true, '2026-05-12 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000009'::uuid, 'student.cs02.demo@vinuni.edu.vn', 'CS102', '2026-SPRING', null, 'completed', 1, false, null::uuid, 7.20::numeric, 3.00::numeric, 'B', true, 4, true, '2026-05-12 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000010'::uuid, 'student.cs02.demo@vinuni.edu.vn', 'CS201', '2026-SUMMER', 'CS201-A', 'enrolled', 1, false, null::uuid, null::numeric, null::numeric, null, false, 0, false, null::timestamptz),
        ('13000000-13ae-4000-8000-000000000011'::uuid, 'student.cs02.demo@vinuni.edu.vn', 'MATH102', '2026-SUMMER', 'MATH102-A', 'enrolled', 1, false, null::uuid, null::numeric, null::numeric, null, false, 0, false, null::timestamptz),
        ('13000000-13ae-4000-8000-000000000012'::uuid, 'student.business.demo@vinuni.edu.vn', 'GEN101', '2025-FALL', null, 'completed', 1, false, null::uuid, 7.80::numeric, 3.00::numeric, 'B', true, 2, true, '2025-12-20 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000013'::uuid, 'student.business.demo@vinuni.edu.vn', 'BUS101', '2026-SPRING', null, 'completed', 1, false, null::uuid, 8.10::numeric, 3.30::numeric, 'B+', true, 3, true, '2026-05-12 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000014'::uuid, 'student.business.demo@vinuni.edu.vn', 'ECON101', '2026-SPRING', null, 'completed', 1, false, null::uuid, 7.00::numeric, 2.70::numeric, 'B-', true, 3, true, '2026-05-12 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000015'::uuid, 'student.business.demo@vinuni.edu.vn', 'BUS201', '2026-SPRING', null, 'failed', 1, false, null::uuid, 3.80::numeric, 0.00::numeric, 'F', false, 0, false, '2026-05-12 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000016'::uuid, 'student.business.demo@vinuni.edu.vn', 'BUS201', '2026-SUMMER', 'BUS201-A', 'retaking', 2, false, '13000000-13ae-4000-8000-000000000015'::uuid, null::numeric, null::numeric, null, false, 0, false, null::timestamptz),
        ('13000000-13ae-4000-8000-000000000017'::uuid, 'student.health.demo@vinuni.edu.vn', 'GEN102', '2026-SPRING', null, 'completed', 1, false, null::uuid, 8.50::numeric, 3.70::numeric, 'A-', true, 2, true, '2026-05-12 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000018'::uuid, 'student.health.demo@vinuni.edu.vn', 'BIO101', '2026-SPRING', null, 'completed', 1, false, null::uuid, 7.40::numeric, 3.00::numeric, 'B', true, 3, true, '2026-05-12 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000019'::uuid, 'student.health.demo@vinuni.edu.vn', 'HS101', '2026-SUMMER', 'HS101-A', 'enrolled', 1, false, null::uuid, null::numeric, null::numeric, null, false, 0, false, null::timestamptz),
        ('13000000-13ae-4000-8000-000000000020'::uuid, 'student.health.demo@vinuni.edu.vn', 'PE101', '2026-SUMMER', 'PE101-A', 'completed', 1, false, null::uuid, null::numeric, null::numeric, 'P', true, 0, false, '2026-07-10 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000021'::uuid, 'student.liberal.demo@vinuni.edu.vn', 'GEN101', '2026-SPRING', null, 'failed', 1, false, null::uuid, 2.80::numeric, 0.00::numeric, 'F', false, 0, true, '2026-05-12 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000022'::uuid, 'student.liberal.demo@vinuni.edu.vn', 'GEN102', '2026-SUMMER', 'GEN102-A', 'completed', 1, false, null::uuid, 8.20::numeric, 3.30::numeric, 'B+', true, 2, true, '2026-07-10 10:00:00+07'::timestamptz),
        ('13000000-13ae-4000-8000-000000000023'::uuid, 'student.liberal.demo@vinuni.edu.vn', 'PE101', '2026-SUMMER', 'PE101-A', 'completed', 1, false, null::uuid, null::numeric, null::numeric, 'P', true, 0, false, '2026-07-10 10:00:00+07'::timestamptz)
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
    seed.grade_10,
    seed.grade_4,
    seed.letter_grade,
    seed.passed,
    seed.earned_credits,
    seed.is_gpa_counted,
    seed.completed_at
from enrollment_seed seed
join users u on u.email = seed.student_email
join student_profiles sp on sp.user_id = u.id
join courses c
  on c.code = seed.course_code
 and c.semester = 'Summer 2026'
 and c.academic_year = '2026'
join academic_terms t on t.code = seed.term_code
left join course_sections cs
  on cs.course_id = c.id
 and cs.term_id = t.id
 and cs.section_code = seed.section_code
on conflict (student_id, course_id, term_id, attempt_no) do update
set
    section_id = excluded.section_id,
    status = excluded.status,
    is_improvement = excluded.is_improvement,
    retake_of_enrollment_id = excluded.retake_of_enrollment_id,
    grade_10 = excluded.grade_10,
    grade_4 = excluded.grade_4,
    letter_grade = excluded.letter_grade,
    passed = excluded.passed,
    earned_credits = excluded.earned_credits,
    is_gpa_counted = excluded.is_gpa_counted,
    completed_at = excluded.completed_at;

with meeting_seed (
    section_code,
    title,
    meeting_type,
    start_at,
    end_at,
    building,
    room_name,
    note
) as (
    values
        ('GEN101-A', 'Academic English Lecture 1', 'lecture', '2026-06-03 09:00:00+07'::timestamptz, '2026-06-03 10:30:00+07'::timestamptz, 'Academic Building A', 'A101', 'Mock summer lecture.'),
        ('GEN101-A', 'Academic English Seminar', 'seminar', '2026-06-10 13:00:00+07'::timestamptz, '2026-06-10 14:30:00+07'::timestamptz, 'Academic Building A', 'A102', 'Mock writing seminar.'),
        ('GEN101-A', 'Academic English Assignment 1 Deadline', 'deadline', '2026-06-21 23:45:00+07'::timestamptz, '2026-06-22 00:00:00+07'::timestamptz, null, null, 'Mock LMS deadline.'),
        ('GEN102-A', 'Critical Thinking Lecture 1', 'lecture', '2026-06-04 09:00:00+07'::timestamptz, '2026-06-04 10:30:00+07'::timestamptz, 'Academic Building A', 'A101', 'Mock summer lecture.'),
        ('GEN102-A', 'Critical Thinking Quiz 1', 'exam', '2026-06-18 09:00:00+07'::timestamptz, '2026-06-18 10:00:00+07'::timestamptz, 'Academic Building A', 'A101', 'Mock quiz.'),
        ('MATH102-A', 'Discrete Mathematics Lecture', 'lecture', '2026-06-02 10:45:00+07'::timestamptz, '2026-06-02 12:15:00+07'::timestamptz, 'Academic Building A', 'A102', 'Mock summer lecture.'),
        ('MATH102-A', 'Discrete Mathematics Tutorial', 'tutorial', '2026-06-09 14:45:00+07'::timestamptz, '2026-06-09 16:15:00+07'::timestamptz, 'Academic Building A', 'A102', 'Mock problem-solving tutorial.'),
        ('CS101-A', 'Programming Lecture', 'lecture', '2026-06-02 09:00:00+07'::timestamptz, '2026-06-02 10:30:00+07'::timestamptz, 'Academic Building A', 'A101', 'Mock summer lecture.'),
        ('CS101-A', 'Programming Lab', 'lab', '2026-06-04 13:00:00+07'::timestamptz, '2026-06-04 15:00:00+07'::timestamptz, 'Computer Science Lab', 'CSL1', 'Mock programming lab.'),
        ('CS101-A', 'Programming Office Hour', 'office_hour', '2026-06-11 16:00:00+07'::timestamptz, '2026-06-11 17:00:00+07'::timestamptz, 'Faculty Office', 'FOH1', 'Mock office hour.'),
        ('CS102-A', 'Data Structures Lecture', 'lecture', '2026-06-03 10:45:00+07'::timestamptz, '2026-06-03 12:15:00+07'::timestamptz, 'Academic Building A', 'A102', 'Mock summer lecture.'),
        ('CS102-A', 'Data Structures Lab', 'lab', '2026-06-05 13:00:00+07'::timestamptz, '2026-06-05 15:00:00+07'::timestamptz, 'Computer Science Lab', 'CSL1', 'Mock lab.'),
        ('CS102-A', 'Data Structures Midterm Exam', 'exam', '2026-06-30 09:00:00+07'::timestamptz, '2026-06-30 11:00:00+07'::timestamptz, 'Academic Building A', 'A101', 'Mock midterm exam.'),
        ('CS102-A', 'Data Structures Assignment Deadline', 'deadline', '2026-07-07 23:45:00+07'::timestamptz, '2026-07-08 00:00:00+07'::timestamptz, null, null, 'Mock LMS deadline.'),
        ('CS102-A', 'Data Structures Final Exam', 'exam', '2026-07-28 09:00:00+07'::timestamptz, '2026-07-28 11:00:00+07'::timestamptz, 'Academic Building A', 'A101', 'Mock final exam.'),
        ('CS201-A', 'Algorithms Lecture', 'lecture', '2026-06-08 09:00:00+07'::timestamptz, '2026-06-08 10:30:00+07'::timestamptz, 'Academic Building A', 'A102', 'Mock algorithms lecture.'),
        ('CS201-A', 'Algorithms Quiz 1', 'exam', '2026-06-22 09:00:00+07'::timestamptz, '2026-06-22 10:00:00+07'::timestamptz, 'Academic Building A', 'A102', 'Mock quiz.'),
        ('CS301-A', 'Database Systems Lecture', 'lecture', '2026-06-09 09:00:00+07'::timestamptz, '2026-06-09 10:30:00+07'::timestamptz, 'Academic Building A', 'A101', 'Mock database lecture.'),
        ('CS301-A', 'Database Systems Lab', 'lab', '2026-06-12 13:00:00+07'::timestamptz, '2026-06-12 15:00:00+07'::timestamptz, 'Computer Science Lab', 'CSL1', 'Mock database lab.'),
        ('BUS101-A', 'Management Lecture', 'lecture', '2026-06-03 14:45:00+07'::timestamptz, '2026-06-03 16:15:00+07'::timestamptz, 'Business School', 'B204', 'Mock management lecture.'),
        ('BUS201-A', 'Marketing Fundamentals Seminar', 'seminar', '2026-06-05 09:00:00+07'::timestamptz, '2026-06-05 10:30:00+07'::timestamptz, 'Business School', 'B204', 'Mock marketing seminar.'),
        ('BUS201-A', 'Marketing Project Deadline', 'deadline', '2026-07-14 23:45:00+07'::timestamptz, '2026-07-15 00:00:00+07'::timestamptz, null, null, 'Mock project deadline.'),
        ('BIO101-A', 'Human Biology Lab', 'lab', '2026-06-04 09:00:00+07'::timestamptz, '2026-06-04 11:00:00+07'::timestamptz, 'Health Sciences Lab', 'H201', 'Mock biology lab.'),
        ('HS101-A', 'Public Health Lecture', 'lecture', '2026-06-10 10:45:00+07'::timestamptz, '2026-06-10 12:15:00+07'::timestamptz, 'Academic Building A', 'A102', 'Mock public health lecture.'),
        ('HS101-A', 'Public Health Final Exam', 'exam', '2026-07-29 09:00:00+07'::timestamptz, '2026-07-29 11:00:00+07'::timestamptz, 'Academic Building A', 'A102', 'Mock final exam.'),
        ('PE101-A', 'Physical Education Session', 'lab', '2026-06-06 08:00:00+07'::timestamptz, '2026-06-06 09:30:00+07'::timestamptz, 'Sports Complex', 'Gym 1', 'Mock PE activity.'),
        ('CAP401-A', 'Capstone Proposal Seminar', 'seminar', '2026-07-03 14:00:00+07'::timestamptz, '2026-07-03 16:00:00+07'::timestamptz, 'Academic Building A', 'A101', 'Mock capstone seminar.')
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
    seed.title,
    seed.meeting_type,
    seed.start_at,
    seed.end_at,
    r.id,
    seed.note
from meeting_seed seed
join course_sections cs on cs.section_code = seed.section_code
join academic_terms t on t.id = cs.term_id and t.code = '2026-SUMMER'
left join rooms r on r.building = seed.building and r.room_name = seed.room_name
on conflict (section_id, title, start_at) do update
set
    meeting_type = excluded.meeting_type,
    end_at = excluded.end_at,
    room_id = excluded.room_id,
    note = excluded.note;
