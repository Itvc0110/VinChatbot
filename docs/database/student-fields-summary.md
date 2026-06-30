# Student Fields Summary

Tài liệu này tổng hợp các field chính liên quan đến một sinh viên trong database và Student API.
Nguồn chính: `migrations/000002_initial_app_schema.sql`, `migrations/000004_forum_schema.sql`,
`migrations/000005_admin_notification_workflow.sql`, `migrations/000007_academic_demo_database_core.sql`,
và `vinchatbot/app/schemas/students.py`.

## Tổng quan

Một sinh viên không nằm trong một bảng duy nhất. Dữ liệu được tách theo nhóm:

- Thông tin tài khoản: `users`
- Hồ sơ sinh viên: `student_profiles`
- Viện/trường trực thuộc: `institutes`
- Tổng kết học thuật/GPA: `academic_summaries`
- Môn học và đăng ký học: `courses`, `enrollments`
- Lịch học/lịch thi/sự kiện cá nhân: `schedules`
- Deadline học tập: `deadlines`
- Thông báo và trạng thái đọc: `notifications`, `notification_reads`
- Gợi ý câu hỏi cá nhân hóa: `suggested_questions`

Nếu chỉ tính hồ sơ sinh viên cốt lõi, bảng chính là `student_profiles`, join với
`users`, `institutes`, và `academic_summaries`.

## 1. `users`

Thông tin tài khoản đăng nhập của sinh viên.

| Field | Type | Required | Ghi chú |
| --- | --- | --- | --- |
| `id` | `uuid` | Yes | Primary key, tự sinh bằng `gen_random_uuid()`. |
| `email` | `text` | Yes | Email đăng nhập, unique. |
| `password_hash` | `text` | No | Hash mật khẩu, không trả về API. |
| `full_name` | `text` | Yes | Họ tên đầy đủ. |
| `preferred_name` | `text` | No | Tên muốn được gọi. |
| `phone` | `text` | No | Số điện thoại. |
| `avatar_url` | `text` | No | URL ảnh đại diện. |
| `status` | `text` | Yes | `active`, `inactive`, hoặc `suspended`. |
| `created_at` | `timestamptz` | Yes | Thời điểm tạo tài khoản. |
| `updated_at` | `timestamptz` | Yes | Thời điểm cập nhật gần nhất. |

Ghi chú: tất cả field trên là **cũ** so với Phase 13A. Không có field mới được thêm vào `users`.

## 2. `student_profiles`

Bảng hồ sơ sinh viên chính.

| Field | Type | Required | Ghi chú |
| --- | --- | --- | --- |
| `id` | `uuid` | Yes | Primary key của hồ sơ sinh viên. |
| `user_id` | `uuid` | Yes | FK đến `users.id`, unique, mỗi user có tối đa một profile sinh viên. |
| `student_id` | `text` | Yes | Mã số sinh viên, unique. |
| `institute_id` | `uuid` | Yes | FK đến `institutes.id`. |
| `program` | `text` | No | Chương trình học. |
| `major` | `text` | No | Ngành/chuyên ngành. |
| `cohort` | `integer` | No | Khóa/cohort của sinh viên. |
| `academic_year` | `integer` | No | Năm học hiện tại theo profile. |
| `student_status` | `text` | Yes | `active`, `inactive`, `leave`, `graduated`, hoặc `withdrawn`. |
| `preferred_language` | `text` | Yes | `vi` hoặc `en`. |
| `advisor_name` | `text` | No | Tên cố vấn học tập. |
| `advisor_email` | `text` | No | Email cố vấn học tập. |
| `ai_personalization_enabled` | `boolean` | Yes | Bật/tắt cá nhân hóa AI. |
| `created_at` | `timestamptz` | Yes | Thời điểm tạo profile. |
| `updated_at` | `timestamptz` | Yes | Thời điểm cập nhật profile gần nhất. |

Field mới thêm ở Phase 13A:

| Field | Type | Ghi chú |
| --- | --- | --- |
| `student_code` | `text` | Mã sinh viên chuẩn hóa. |
| `full_name` | `text` | Họ tên đầy đủ, tách rõ khỏi `users.full_name`. |
| `faculty_id` | `uuid` | FK đến `faculties.id`. |
| `program_id` | `uuid` | FK đến `programs.id`. |
| `cohort_year` | `integer` | Năm khóa/cohort chuẩn hóa. |
| `current_year` | `integer` | Năm học hiện tại chuẩn hóa. |
| `status` | `text` | Trạng thái sinh viên chuẩn hóa. |

## 3. `institutes`

Thông tin viện/trường của sinh viên.

| Field | Type | Required | Ghi chú |
| --- | --- | --- | --- |
| `id` | `uuid` | Yes | Primary key. |
| `code` | `text` | Yes | Mã viện/trường, unique. Ví dụ: `VIB`, `CECS`, `CHS`, `CASE`. |
| `name_vi` | `text` | Yes | Tên tiếng Việt. |
| `name_en` | `text` | Yes | Tên tiếng Anh. |

## 4. `academic_summaries`

Tổng kết học thuật của một sinh viên. Đây là bảng chứa `gpa`/điểm trung bình.

| Field | Type | Required | Ghi chú |
| --- | --- | --- | --- |
| `id` | `uuid` | Yes | Primary key. |
| `student_profile_id` | `uuid` | Yes | FK đến `student_profiles.id`, unique. |
| `gpa` | `numeric(3,2)` | No | GPA từ `0.00` đến `4.00`. |
| `credits_earned` | `integer` | Yes | Số tín chỉ đã tích lũy. |
| `credits_required` | `integer` | Yes | Số tín chỉ cần hoàn thành, mặc định `120`. |
| `current_semester` | `text` | No | Học kỳ hiện tại. |
| `academic_status` | `text` | Yes | `normal`, `warning`, `probation`, hoặc `suspended`. |
| `updated_at` | `timestamptz` | Yes | Thời điểm cập nhật học thuật gần nhất. |

## 5. `enrollments`

Quan hệ sinh viên đăng ký môn học.

| Field | Type | Required | Ghi chú |
| --- | --- | --- | --- |
| `id` | `uuid` | Yes | Primary key. |
| `student_profile_id` | `uuid` | Yes | FK đến `student_profiles.id`. |
| `course_id` | `uuid` | Yes | FK đến `courses.id`. |
| `status` | `text` | Yes | `enrolled`, `completed`, `dropped`, hoặc `waitlisted`. |
| `created_at` | `timestamptz` | Yes | Thời điểm tạo enrollment. |

## 6. `courses`

Thông tin môn học mà sinh viên có thể được enroll.

| Field | Type | Required | Ghi chú |
| --- | --- | --- | --- |
| `id` | `uuid` | Yes | Primary key. |
| `institute_id` | `uuid` | No | FK đến `institutes.id`. |
| `course_code` | `text` | Yes | Mã môn học. |
| `course_title` | `text` | Yes | Tên môn học. |
| `credits` | `integer` | Yes | Số tín chỉ, mặc định `3`. |
| `semester` | `text` | No | Học kỳ. |
| `academic_year` | `text` | No | Năm học. |
| `instructor` | `text` | No | Giảng viên. |
| `is_active` | `boolean` | Yes | Môn còn active hay không. |

Field mới thêm ở Phase 13A:

| Field | Type | Ghi chú |
| --- | --- | --- |
| `code` | `text` | Mã môn chuẩn hóa. |
| `name` | `text` | Tên môn chuẩn hóa. |
| `course_level` | `integer` | Mức độ môn học. |
| `department_code` | `text` | Mã bộ môn/khoa phụ trách. |
| `is_general_education` | `boolean` | Có phải môn đại cương không. |
| `description` | `text` | Mô tả môn học. |

## 7. `schedules`

Lịch cá nhân của sinh viên, bao gồm lớp học, lab, exam, office hour, meeting, event.

| Field | Type | Required | Ghi chú |
| --- | --- | --- | --- |
| `id` | `uuid` | Yes | Primary key. |
| `student_profile_id` | `uuid` | Yes | FK đến `student_profiles.id`. |
| `course_id` | `uuid` | No | FK đến `courses.id`, có thể null. |
| `title` | `text` | Yes | Tiêu đề lịch. |
| `schedule_type` | `text` | Yes | `class`, `lab`, `exam`, `office_hour`, `meeting`, `event`, hoặc `other`. |
| `start_time` | `timestamptz` | Yes | Thời gian bắt đầu. |
| `end_time` | `timestamptz` | Yes | Thời gian kết thúc, phải sau `start_time`. |
| `location` | `text` | No | Địa điểm. |
| `building` | `text` | No | Tòa nhà. |
| `room` | `text` | No | Phòng. |
| `instructor` | `text` | No | Giảng viên/người phụ trách. |
| `recurrence_rule` | `text` | No | Quy tắc lặp lịch nếu có. |

## 8. `deadlines`

Deadline học tập của sinh viên.

| Field | Type | Required | Ghi chú |
| --- | --- | --- | --- |
| `id` | `uuid` | Yes | Primary key. |
| `student_profile_id` | `uuid` | No | FK đến `student_profiles.id`. |
| `course_id` | `uuid` | No | FK đến `courses.id`. |
| `title` | `text` | Yes | Tiêu đề deadline. |
| `kind` | `text` | No | Loại deadline. |
| `due_at` | `timestamptz` | Yes | Thời hạn. |
| `source_title` | `text` | No | Tên nguồn/thông báo gốc. |
| `source_url` | `text` | No | URL nguồn. |

## 9. `notifications`

Thông báo có thể target đến sinh viên theo `all`, `institute`, `course`, `cohort`, hoặc `student`.

| Field | Type | Required | Ghi chú |
| --- | --- | --- | --- |
| `id` | `uuid` | Yes | Primary key. |
| `type` | `text` | Yes | `announcement`, `deadline`, `event`, `academic`, `schedule`, `student_services`, `system`, `emergency`, hoặc `forum`. |
| `title` | `text` | Yes | Tiêu đề thông báo. |
| `message` | `text` | Yes | Nội dung thông báo. |
| `priority` | `text` | Yes | `low`, `medium`, `high`, hoặc `urgent`. |
| `status` | `text` | Yes | `draft`, `scheduled`, `published`, hoặc `archived`. |
| `target_scope` | `text` | Yes | `all`, `institute`, `course`, `cohort`, hoặc `student`. |
| `institute_id` | `uuid` | No | Target theo viện/trường. |
| `course_id` | `uuid` | No | Target theo môn học. |
| `cohort` | `integer` | No | Target theo khóa/cohort. |
| `recipient_user_id` | `uuid` | No | Target trực tiếp một user sinh viên. |
| `deadline` | `timestamptz` | No | Deadline gắn với thông báo. |
| `event_date` | `timestamptz` | No | Ngày sự kiện. |
| `start_date` | `timestamptz` | No | Thời điểm bắt đầu hiển thị. |
| `end_date` | `timestamptz` | No | Thời điểm hết hiệu lực. |
| `source_title` | `text` | No | Tên nguồn. |
| `source_url` | `text` | No | URL nguồn. |
| `created_by` | `uuid` | No | User tạo thông báo. |
| `forum_topic_id` | `uuid` | No | Topic forum liên quan, nếu có. |
| `forum_comment_id` | `uuid` | No | Comment forum liên quan, nếu có. |
| `created_at` | `timestamptz` | Yes | Thời điểm tạo. |
| `updated_at` | `timestamptz` | Yes | Thời điểm cập nhật. |

## 10. `notification_reads`

Trạng thái đọc/lưu trữ thông báo của từng sinh viên.

| Field | Type | Required | Ghi chú |
| --- | --- | --- | --- |
| `id` | `uuid` | Yes | Primary key. |
| `notification_id` | `uuid` | Yes | FK đến `notifications.id`. |
| `user_id` | `uuid` | Yes | FK đến `users.id`. |
| `read_at` | `timestamptz` | Yes | Thời điểm đánh dấu đã đọc. |
| `important` | `boolean` | Yes | Đánh dấu quan trọng. |
| `archived` | `boolean` | Yes | Đã lưu trữ/ẩn khỏi view chính. |

## 11. `suggested_questions`

Nguồn câu hỏi gợi ý cho sinh viên. API `/suggestions/me` lọc theo viện, môn học, cohort,
notification và thời hạn hiệu lực.

| Field | Type | Required | Ghi chú |
| --- | --- | --- | --- |
| `id` | `uuid` | Yes | Primary key. |
| `question_text` | `text` | Yes | Nội dung câu hỏi gợi ý. |
| `source_type` | `text` | Yes | `trend`, `notification`, `admin`, `ai`, hoặc `manual`. |
| `source_id` | `uuid` | No | ID nguồn gợi ý. |
| `notification_id` | `uuid` | No | FK đến `notifications.id`. |
| `topic` | `text` | No | Chủ đề. |
| `intent` | `text` | No | Ý định/cụm intent. |
| `category` | `text` | No | Nhóm hiển thị. |
| `trigger_phase` | `text` | No | Giai đoạn kích hoạt gợi ý. |
| `institute_id` | `uuid` | No | Scope theo viện/trường. |
| `course_id` | `uuid` | No | Scope theo môn học. |
| `cohort` | `integer` | No | Scope theo cohort. |
| `score` | `numeric(6,3)` | Yes | Điểm ranking. |
| `priority` | `integer` | Yes | Độ ưu tiên. |
| `created_by_ai` | `boolean` | Yes | Có được tạo bởi AI không. |
| `approved_by_admin` | `boolean` | Yes | Admin đã duyệt chưa. |
| `is_active` | `boolean` | Yes | Gợi ý đang active hay không. |
| `valid_from` | `timestamptz` | No | Bắt đầu hiệu lực. |
| `valid_until` | `timestamptz` | No | Kết thúc hiệu lực. |
| `created_at` | `timestamptz` | Yes | Thời điểm tạo. |
| `updated_at` | `timestamptz` | Yes | Thời điểm cập nhật. |

## 12. Activity Data liên quan đến sinh viên

Các bảng dưới đây không phải là profile học vụ cốt lõi, nhưng vẫn liên quan đến một sinh viên
thông qua `user_id`, `student_profile_id`, hoặc các quan hệ dẫn xuất.

### Chat history

| Table | Field | Type | Ghi chú |
| --- | --- | --- | --- |
| `conversations` | `id` | `uuid` | Primary key của cuộc trò chuyện. |
| `conversations` | `user_id` | `uuid` | FK đến `users.id`, chủ cuộc trò chuyện. |
| `conversations` | `title` | `text` | Tiêu đề cuộc trò chuyện. |
| `conversations` | `title_manual` | `boolean` | Tiêu đề do user chỉnh thủ công hay không. |
| `conversations` | `topic` | `text` | Chủ đề hội thoại. |
| `conversations` | `created_at` | `timestamptz` | Thời điểm tạo. |
| `conversations` | `updated_at` | `timestamptz` | Thời điểm cập nhật. |
| `conversations` | `last_message_at` | `timestamptz` | Thời điểm tin nhắn cuối. |
| `messages` | `id` | `uuid` | Primary key của tin nhắn. |
| `messages` | `conversation_id` | `uuid` | FK đến `conversations.id`. |
| `messages` | `role` | `text` | `user`, `assistant`, `system`, hoặc `tool`. |
| `messages` | `content` | `text` | Nội dung tin nhắn. |
| `messages` | `answer_json` | `jsonb` | Cấu trúc câu trả lời nếu có. |
| `messages` | `intent` | `text` | Intent được nhận diện. |
| `messages` | `topic` | `text` | Topic được nhận diện. |
| `messages` | `confidence` | `numeric(4,3)` | Độ tin cậy từ `0` đến `1`. |
| `messages` | `needs_human_review` | `boolean` | Có cần người kiểm tra không. |
| `messages` | `created_at` | `timestamptz` | Thời điểm tạo tin nhắn. |

### Support tickets

| Table | Field | Type | Ghi chú |
| --- | --- | --- | --- |
| `tickets` | `id` | `uuid` | Primary key của ticket. |
| `tickets` | `student_profile_id` | `uuid` | FK đến `student_profiles.id`. |
| `tickets` | `institute_id` | `uuid` | FK đến `institutes.id`. |
| `tickets` | `subject` | `text` | Tiêu đề ticket. |
| `tickets` | `body` | `text` | Nội dung ticket. |
| `tickets` | `department` | `text` | Phòng ban xử lý. |
| `tickets` | `category` | `text` | Nhóm vấn đề. |

## 13. Academic demo core mới ở Phase 13A

Các bảng dưới đây là schema mới được thêm cho dữ liệu học thuật demo:

### `faculties`

| Field | Type | Ghi chú |
| --- | --- | --- |
| `id` | `uuid` | Primary key. |
| `code` | `text` | Mã faculty. |
| `name` | `text` | Tên faculty. |

### `programs`

| Field | Type | Ghi chú |
| --- | --- | --- |
| `id` | `uuid` | Primary key. |
| `faculty_id` | `uuid` | FK đến `faculties.id`. |
| `code` | `text` | Mã chương trình. |
| `name` | `text` | Tên chương trình. |
| `degree_level` | `text` | Bậc đào tạo. |
| `curriculum_year` | `integer` | Năm curriculum. |
| `total_required_credits` | `integer` | Tổng tín chỉ cần hoàn thành. |

### `academic_terms`

| Field | Type | Ghi chú |
| --- | --- | --- |
| `id` | `uuid` | Primary key. |
| `code` | `text` | Mã term. |
| `name` | `text` | Tên term. |
| `start_date` | `date` | Ngày bắt đầu. |
| `end_date` | `date` | Ngày kết thúc. |
| `academic_year` | `integer` | Năm học. |
| `term_order` | `integer` | Thứ tự term. |

### `curriculum_courses`

| Field | Type | Ghi chú |
| --- | --- | --- |
| `program_id` | `uuid` | FK đến `programs.id`. |
| `course_id` | `uuid` | FK đến `courses.id`. |
| `category` | `text` | `general_education`, `foundation`, `major_core`, `major_elective`, `physical_education`, `capstone`. |
| `is_required` | `boolean` | Bắt buộc hay tự chọn. |
| `suggested_year` | `integer` | Năm học gợi ý. |
| `suggested_term` | `integer` | Term gợi ý. |
| `min_required_grade_4` | `numeric` | Điểm tối thiểu trên thang 4. |

### `course_requisites`

| Field | Type | Ghi chú |
| --- | --- | --- |
| `course_id` | `uuid` | Môn đang xét. |
| `required_course_id` | `uuid` | Môn điều kiện. |
| `requisite_type` | `text` | `prerequisite` hoặc `corequisite`. |
| `min_grade_4` | `numeric` | Điểm tối thiểu của môn điều kiện. |
| `note` | `text` | Ghi chú bổ sung. |

### `student_course_enrollments`

| Field | Type | Ghi chú |
| --- | --- | --- |
| `student_id` | `uuid` | FK đến `student_profiles.id`. |
| `course_id` | `uuid` | FK đến `courses.id`. |
| `term_id` | `uuid` | FK đến `academic_terms.id`. |
| `section_id` | `uuid` | FK nullable đến `course_sections.id`. |
| `status` | `text` | `planned`, `enrolled`, `completed`, `failed`, `withdrawn`, `retaking`, `improvement`. |
| `attempt_no` | `integer` | Số lần học. |
| `is_improvement` | `boolean` | Có phải lần học cải thiện điểm không. |
| `retake_of_enrollment_id` | `uuid` | FK tự tham chiếu đến lần học trước. |
| `grade_10` | `numeric` | Điểm thang 10. |
| `grade_4` | `numeric` | Điểm thang 4. |
| `letter_grade` | `text` | Điểm chữ. |
| `passed` | `boolean` | Qua hay rớt. |
| `earned_credits` | `integer` | Tín chỉ tích lũy từ enrollment này. |
| `is_gpa_counted` | `boolean` | Có được tính vào GPA/CPA không. |
| `completed_at` | `timestamptz` | Thời điểm hoàn tất. |

### `rooms`

| Field | Type | Ghi chú |
| --- | --- | --- |
| `building` | `text` | Tên tòa nhà. |
| `room_name` | `text` | Tên phòng. |
| `capacity` | `integer` | Sức chứa. |

### `course_sections`

| Field | Type | Ghi chú |
| --- | --- | --- |
| `course_id` | `uuid` | FK đến `courses.id`. |
| `term_id` | `uuid` | FK đến `academic_terms.id`. |
| `section_code` | `text` | Mã section. |
| `instructor_name` | `text` | Tên giảng viên. |
| `capacity` | `integer` | Sức chứa lớp. |
| `status` | `text` | Trạng thái section. |

### `class_meetings`

| Field | Type | Ghi chú |
| --- | --- | --- |
| `section_id` | `uuid` | FK đến `course_sections.id`. |
| `title` | `text` | Tiêu đề buổi học. |
| `meeting_type` | `text` | `lecture`, `lab`, `tutorial`, `seminar`, `exam`, `office_hour`, `deadline`. |
| `start_at` | `timestamptz` | Thời gian bắt đầu. |
| `end_at` | `timestamptz` | Thời gian kết thúc. |
| `room_id` | `uuid` | FK nullable đến `rooms.id`. |
| `note` | `text` | Ghi chú. |
| `tickets` | `priority` | `text` | `low`, `medium`, `high`, hoặc `urgent`. |
| `tickets` | `status` | `text` | `submitted`, `open`, `in_progress`, `waiting_on_student`, `resolved`, hoặc `closed`. |
| `tickets` | `confirmed_by_user` | `boolean` | Sinh viên đã xác nhận tạo ticket. |
| `tickets` | `created_by_ai` | `boolean` | Ticket được AI tạo giúp hay không. |
| `tickets` | `include_chat_context` | `boolean` | Có đính kèm ngữ cảnh chat không. |
| `tickets` | `included_context` | `text` | Ngữ cảnh chat được đính kèm. |
| `tickets` | `source_conversation_id` | `uuid` | Conversation gốc nếu ticket tạo từ chat. |
| `tickets` | `origin_question` | `text` | Câu hỏi ban đầu của sinh viên. |
| `tickets` | `assigned_admin_id` | `uuid` | Admin được assign. |
| `tickets` | `submitted_at` | `timestamptz` | Thời điểm submit. |
| `tickets` | `due_at` | `timestamptz` | Hạn xử lý. |
| `tickets` | `sla_hours` | `integer` | SLA tính theo giờ. |
| `tickets` | `resolution` | `text` | Nội dung xử lý/kết luận. |
| `tickets` | `archived` | `boolean` | Đã archive. |
| `tickets` | `deleted` | `boolean` | Đã soft-delete. |
| `tickets` | `created_at` | `timestamptz` | Thời điểm tạo. |
| `tickets` | `updated_at` | `timestamptz` | Thời điểm cập nhật. |
| `ticket_messages` | `id` | `uuid` | Primary key của message trong ticket. |
| `ticket_messages` | `ticket_id` | `uuid` | FK đến `tickets.id`. |
| `ticket_messages` | `sender_user_id` | `uuid` | User gửi message. |
| `ticket_messages` | `author_type` | `text` | `student`, `admin`, `ai`, hoặc `system`. |
| `ticket_messages` | `body` | `text` | Nội dung message. |
| `ticket_messages` | `created_at` | `timestamptz` | Thời điểm tạo. |
| `ticket_status_history` | `id` | `uuid` | Primary key lịch sử trạng thái. |
| `ticket_status_history` | `ticket_id` | `uuid` | FK đến `tickets.id`. |
| `ticket_status_history` | `old_status` | `text` | Trạng thái cũ. |
| `ticket_status_history` | `new_status` | `text` | Trạng thái mới. |
| `ticket_status_history` | `changed_by` | `uuid` | User thay đổi trạng thái. |
| `ticket_status_history` | `changed_at` | `timestamptz` | Thời điểm thay đổi. |

### Question analytics

| Table | Field | Type | Ghi chú |
| --- | --- | --- | --- |
| `student_question_events` | `id` | `uuid` | Primary key. |
| `student_question_events` | `user_id` | `uuid` | FK đến `users.id`, có thể null khi ẩn danh. |
| `student_question_events` | `conversation_id` | `uuid` | Conversation liên quan. |
| `student_question_events` | `raw_question` | `text` | Câu hỏi gốc. |
| `student_question_events` | `normalized_question` | `text` | Câu hỏi đã chuẩn hóa. |
| `student_question_events` | `intent` | `text` | Intent. |
| `student_question_events` | `topic` | `text` | Topic. |
| `student_question_events` | `institute_id` | `uuid` | Institute liên quan. |
| `student_question_events` | `course_id` | `uuid` | Course liên quan. |
| `student_question_events` | `created_at` | `timestamptz` | Thời điểm ghi nhận. |
| `student_question_events` | `is_anonymized` | `boolean` | Event đã được ẩn danh hay chưa. |

### Forum activity

| Table | Field chính liên quan đến sinh viên | Ghi chú |
| --- | --- | --- |
| `forum_topics` | `author_user_id`, `title`, `content`, `tags`, `attachments`, `is_pinned`, `is_locked`, `view_count`, `deleted`, `created_at`, `updated_at`, `last_activity_at` | Topic do sinh viên/admin tạo. |
| `forum_comments` | `author_user_id`, `topic_id`, `parent_comment_id`, `content`, `is_official`, `deleted`, `created_at`, `updated_at` | Comment trong topic. |
| `forum_votes` | `user_id`, `target_type`, `target_id`, `value`, `created_at` | Vote của user cho topic/comment. |
| `forum_mentions` | `mentioned_user_id`, `created_by`, `topic_id`, `comment_id`, `created_at` | Mention/reply notification. |
| `forum_reports` | `reporter_user_id`, `target_type`, `target_id`, `reason`, `status`, `resolved_by`, `resolved_at`, `created_at` | Report nội dung forum. |

## Student API Response Fields

Các endpoint chính đang trả dữ liệu cho sinh viên:

| Endpoint | Nhóm field trả về |
| --- | --- |
| `GET /students/me` | Profile sinh viên, institute, academic summary/GPA. |
| `GET /students/me/courses` | Danh sách môn học đã đăng ký. |
| `GET /students/me/schedule` | Lịch học/lịch thi/lịch cá nhân. |
| `GET /students/me/deadlines` | Deadline học tập. |
| `GET /students/me/notifications` | Thông báo visible với `is_read`, `important`, `archived`. |
| `GET /suggestions/me` | Câu hỏi gợi ý theo nhóm `for_you`, `trending_now`, `from_announcements`, `from_events`. |

## Field cốt lõi nên hiển thị trên Student Dashboard

- Nhận dạng: `student_id`, `full_name`, `email`, `avatar_url`
- Học vụ: `program`, `major`, `cohort`, `academic_year`, `student_status`
- Viện/trường: `institute.code`, `institute.name_vi`, `institute.name_en`
- Cố vấn: `advisor_name`, `advisor_email`
- GPA/tín chỉ: `gpa`, `credits_earned`, `credits_required`, `current_semester`, `academic_status`
- Môn học: `course_code`, `course_title`, `credits`, `semester`, `academic_year`, `instructor`
- Lịch: `title`, `schedule_type`, `start_time`, `end_time`, `location`, `building`, `room`
- Deadline: `title`, `kind`, `due_at`, `course_code`, `source_url`
- Notification: `type`, `title`, `message`, `priority`, `deadline`, `event_date`, `is_read`
- Personalization: `preferred_language`, `ai_personalization_enabled`
