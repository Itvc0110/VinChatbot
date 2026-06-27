-- Phase 12A forum foundation demo seed.
-- Keeps forum readable immediately after migrations without requiring write workflows.

insert into forum_categories (
    slug, name_en, name_vi, description_en, description_vi, color, sort_order, is_active
)
values
    (
        'academic-qa',
        'Academic Q&A',
        'Hỏi đáp học thuật',
        'Questions about courses, registration, advising and academic policy.',
        'Câu hỏi về môn học, đăng ký, cố vấn và quy định học thuật.',
        '#0b6bcb',
        10,
        true
    ),
    (
        'campus-life',
        'Campus Life',
        'Đời sống sinh viên',
        'Student life, clubs, events and practical campus tips.',
        'Đời sống sinh viên, câu lạc bộ, sự kiện và mẹo sinh hoạt trong trường.',
        '#10b981',
        20,
        true
    ),
    (
        'scholarships-opportunities',
        'Scholarships & Opportunities',
        'Học bổng và cơ hội',
        'Scholarships, internships, exchanges and career opportunities.',
        'Học bổng, thực tập, trao đổi và cơ hội nghề nghiệp.',
        '#b45309',
        30,
        true
    ),
    (
        'it-student-services',
        'IT / Student Services',
        'CNTT / Dịch vụ sinh viên',
        'Help with accounts, Wi-Fi, student services and campus systems.',
        'Hỗ trợ tài khoản, Wi-Fi, dịch vụ sinh viên và hệ thống trong trường.',
        '#64748b',
        40,
        true
    )
on conflict (slug) do update
set
    name_en = excluded.name_en,
    name_vi = excluded.name_vi,
    description_en = excluded.description_en,
    description_vi = excluded.description_vi,
    color = excluded.color,
    sort_order = excluded.sort_order,
    is_active = excluded.is_active;

insert into forum_topics (
    id, category_id, author_user_id, title, content, tags, is_pinned, is_locked,
    view_count, deleted, created_at, updated_at, last_activity_at
)
values
    (
        '11111111-120a-4000-8000-000000000001',
        (select id from forum_categories where slug = 'academic-qa'),
        (select id from users where email = 'student.cs.demo@vinuni.edu.vn'),
        'How do I prepare for add/drop week?',
        'I am checking my Fall 2026 schedule and want to understand what to review before add/drop week starts.',
        array['registration', 'advising', 'fall-2026'],
        true,
        false,
        24,
        false,
        now() - interval '10 days',
        now() - interval '2 days',
        now() - interval '2 days'
    ),
    (
        '11111111-120a-4000-8000-000000000002',
        (select id from forum_categories where slug = 'campus-life'),
        (select id from users where email = 'student.business.demo@vinuni.edu.vn'),
        'Good study spots during project season',
        'Which campus spaces are usually quiet enough for group project work in the afternoon?',
        array['campus', 'study-groups'],
        false,
        false,
        18,
        false,
        now() - interval '8 days',
        now() - interval '1 day',
        now() - interval '1 day'
    ),
    (
        '11111111-120a-4000-8000-000000000003',
        (select id from forum_categories where slug = 'scholarships-opportunities'),
        (select id from users where email = 'student.health.demo@vinuni.edu.vn'),
        'Where are exchange opportunity deadlines posted?',
        'I want to follow exchange and scholarship deadlines without missing official announcements.',
        array['scholarships', 'exchange'],
        false,
        false,
        12,
        false,
        now() - interval '6 days',
        now() - interval '6 days',
        now() - interval '6 days'
    ),
    (
        '11111111-120a-4000-8000-000000000004',
        (select id from forum_categories where slug = 'it-student-services'),
        (select id from users where email = 'student.liberal.demo@vinuni.edu.vn'),
        'What should I check before reporting portal login issues?',
        'Before opening a ticket, what details should I collect for a student portal login problem?',
        array['portal', 'student-services'],
        false,
        false,
        9,
        false,
        now() - interval '4 days',
        now() - interval '12 hours',
        now() - interval '12 hours'
    )
on conflict (id) do update
set
    category_id = excluded.category_id,
    author_user_id = excluded.author_user_id,
    title = excluded.title,
    content = excluded.content,
    tags = excluded.tags,
    is_pinned = excluded.is_pinned,
    is_locked = excluded.is_locked,
    view_count = excluded.view_count,
    deleted = excluded.deleted,
    updated_at = excluded.updated_at,
    last_activity_at = excluded.last_activity_at;

insert into forum_comments (
    id, topic_id, author_user_id, parent_comment_id, content, is_official, deleted,
    created_at, updated_at
)
values
    (
        '22222222-120a-4000-8000-000000000001',
        '11111111-120a-4000-8000-000000000001',
        (select id from users where email = 'admin.cecs.demo@vinuni.edu.vn'),
        null,
        'Start with your degree plan, prerequisite list and advisor notes. If anything conflicts, contact your institute office before the deadline.',
        true,
        false,
        now() - interval '2 days',
        now() - interval '2 days'
    ),
    (
        '22222222-120a-4000-8000-000000000002',
        '11111111-120a-4000-8000-000000000002',
        (select id from users where email = 'student.cs.demo@vinuni.edu.vn'),
        null,
        'The library discussion rooms are useful if you book early. Some classrooms are also available between scheduled sessions.',
        false,
        false,
        now() - interval '1 day',
        now() - interval '1 day'
    ),
    (
        '22222222-120a-4000-8000-000000000003',
        '11111111-120a-4000-8000-000000000004',
        (select id from users where email = 'admin.global.demo@vinuni.edu.vn'),
        null,
        'Include your account email, screenshot, approximate time, browser, and whether the issue happens on another network.',
        true,
        false,
        now() - interval '10 hours',
        now() - interval '10 hours'
    )
on conflict (id) do update
set
    topic_id = excluded.topic_id,
    author_user_id = excluded.author_user_id,
    parent_comment_id = excluded.parent_comment_id,
    content = excluded.content,
    is_official = excluded.is_official,
    deleted = excluded.deleted,
    updated_at = excluded.updated_at;

update forum_topics t
set official_comment_id = c.id
from forum_comments c
where c.topic_id = t.id
  and c.is_official = true
  and t.id in (
      '11111111-120a-4000-8000-000000000001',
      '11111111-120a-4000-8000-000000000004'
  );
