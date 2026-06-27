insert into roles (code, name)
values
    ('student', 'Student'),
    ('institute_admin', 'Institute Admin'),
    ('global_admin', 'Global Admin'),
    ('staff', 'Staff')
on conflict (code) do update
set name = excluded.name;

insert into institutes (code, name_vi, name_en)
values
    ('VIB', 'Viện Kinh doanh Quản trị', 'College of Business and Management'),
    (
        'CECS',
        'Viện Kỹ thuật và Khoa học Máy tính',
        'College of Engineering and Computer Science'
    ),
    ('CHS', 'Viện Khoa học Sức khỏe', 'College of Health Sciences'),
    (
        'CASE',
        'Viện Khoa học và Giáo dục Khai phóng',
        'College of Arts, Sciences and Education'
    )
on conflict (code) do update
set
    name_vi = excluded.name_vi,
    name_en = excluded.name_en;
