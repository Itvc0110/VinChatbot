-- Admin notification lifecycle and type values.
-- Existing columns already support targeting and query-time scheduling:
-- target_scope/institute_id/cohort plus start_date/end_date.

alter table notifications
    drop constraint if exists notifications_status_check;
alter table notifications
    add constraint notifications_status_check check (
        status in ('draft', 'scheduled', 'published', 'archived')
    );

alter table notifications
    drop constraint if exists notifications_type_check;
alter table notifications
    add constraint notifications_type_check check (
        type in (
            'announcement',
            'deadline',
            'event',
            'academic',
            'schedule',
            'student_services',
            'system',
            'emergency',
            'forum'
        )
    );
