# VinChatbot UI/UX Improvement Prompt

Please inspect the existing project structure first, then modify the actual frontend code. Do not only describe the design. Use the existing framework, routing style, component structure, UI library, and styling conventions already present in the repo.

## Context

This is a **VinUni Student Copilot** web app. The chatbot is named **Vinnie**.

Vinnie supports students with:

* Verified answers from official VinUni sources
* Personalized student support
* Notifications
* Schedule
* Support tickets
* Admin console

---

# Current UI Change Requirements

## 1. Improve Schedule Visualization

Replace the current simple schedule view with a proper calendar-style interface similar to Google Calendar.

### Calendar Requirements

Add a calendar page for students.

The calendar should support at least:

* Week view
* Month view

Day view is optional if easy.

### Calendar Controls

Add controls for:

* Today
* Previous / Next
* Week / Month toggle
* Search events
* Filter by event type

### Event Types

Support these event types:

* Class
* Deadline
* Exam
* Event
* Reminder

### Calendar UI

Show events as colored calendar blocks.

Clicking an event should open a detail popover or side drawer showing:

* Title
* Time
* Location
* Course / category
* Description
* Source if available
* Add reminder button

Add an **Upcoming** side panel or card list showing the next deadlines/classes.

Keep the design polished, clean, and close to Google Calendar UX, while still matching the VinUni Student Copilot visual style.

---

## 2. Remove Tuition Page and Replace It With Notifications

Remove the student navigation item/page for **“Học phí” / Tuition**.

Replace it with **“Thông báo” / Notifications**.

### Notifications Page Requirements

Create a notification inbox.

### Notification Types

Support these notification types:

* Academic
* Schedule
* Deadline
* Event
* Student Services
* System

### Notification Filters

Add filters:

* All
* Unread
* Important
* Academic
* Schedule
* Deadline
* Event
* System

### Notification Item UI

Each notification item should show:

* Title
* Short message
* Type badge
* Read/unread state
* Created time
* Optional related source or action

### Notification Actions

Add actions:

* Mark as read/unread
* Mark as important
* Archive/hide notification
* Delete notification with confirmation

Add empty states and loading/error states.

### Updated Student Sidebar Navigation

Update the student sidebar navigation to show only:

* Tổng quan
* Hỏi AI
* Lịch học
* Thông báo
* Yêu cầu hỗ trợ

Remove **“Học phí”** from the sidebar and any main student quick cards unless still needed by backend.

---

## 3. Improve Support Tickets

Update the support ticket page to make it more useful and demo-ready.

### Ticket List Requirements

Add a ticket list with filters:

* Search by keyword
* Status:

  * All
  * Open
  * In Progress
  * Waiting
  * Resolved
  * Closed
* Priority:

  * All
  * Low
  * Medium
  * High
* Category:

  * Academic
  * Schedule
  * Student Services
  * Technical
  * Other
* Visibility:

  * Active
  * Hidden/Archived
  * Deleted, if supported

### Ticket Item UI

Each ticket item should show:

* Title / question
* Status badge
* Priority badge
* Category
* Created time
* Last updated time
* Short preview

### Ticket Actions

Add ticket actions:

* View detail
* Hide / archive ticket
* Restore hidden ticket
* Delete / remove ticket with confirmation

If the backend does not support permanent deletion, implement delete as a frontend archived/hidden state and name it clearly.

### Ticket Detail

Add a clean ticket detail drawer/page.

Ticket detail should show:

* Original student question
* Conversation history or admin response if available
* Status
* Priority
* Category
* Source/citation if attached
* Actions to update status, hide, or delete

---

## 4. Remove the Chat Mode Toggle

Remove the buttons/tabs:

* “Thông tin chung VinUni”
* “Thông tin của tôi”

The chat should not show this toggle anymore.

### New Behavior

Keep the chat input simple.

The system/backend can decide whether the question needs general official sources or personalized student context.

Add a small subtle privacy/helper note near the chat input:

> Vinnie may use your student profile, schedule, notifications, and official VinUni sources when needed.

Do not make the user manually choose general vs personal mode.

---

## 5. Hide the Source Block by Default

Currently, the source/citation block is always visible on the right side. Change this behavior.

### New Behavior

* The right source panel should be hidden by default.
* The chat area should use the full available width when no source is open.
* Each assistant answer should have a **“Nguồn” / “Sources”** button.
* When the user clicks the **“Nguồn”** button for a specific answer, open the source panel on the right.
* The source panel should show only the sources for the selected assistant answer.
* Add a close button to hide the source panel again.
* On smaller screens, show sources in a slide-over drawer instead of a fixed right column.

### Source Panel Content

The source panel should show:

* Source title
* Source type:

  * PDF
  * URL
  * Database
  * Official page
* Matched section
* Relevant excerpt
* Last crawled time
* Official source status
* Open source button if URL exists

---

## 6. Put Citations Under Each Answer

Change the chat answer design so that citations are attached directly under each assistant message.

### Citation Behavior

For every assistant answer:

1. Show the answer content first.
2. Directly below that same message, show citation chips/cards.

Example:

* `[1] Academic Calendar 2025–2026 · Section: Course Withdrawal · Updated 2 days ago`
* `[2] Student Handbook · Section: Academic Policy · Updated 1 week ago`

### Citation Interaction

* Citation chips should be clickable.
* Clicking a citation should open the right source panel and focus that source.

### No Verified Data State

If the answer has no verified data, show:

> Không có nguồn đối chiếu chính thức.

> Vinnie đã từ chối trả lời thay vì đoán.

Do not show all sources globally in one permanent block.

Sources must be tied to the exact answer they support.

---

## 7. Update Chat Suggested Prompts

Remove tuition-focused suggested prompts from the chat screen.

Use these suggestions instead:

* “What deadlines do I have this week?”
* “When is my next class?”
* “Show my notifications”
* “What events are happening this week?”
* “How do I submit a support request?”
* “What is the course withdrawal process?”

---

## 8. Keep Role-Based UI Clear

Do not mix student and admin navigation.

### Student Sidebar

Student sidebar should only show student features:

* Tổng quan
* Hỏi AI
* Lịch học
* Thông báo
* Yêu cầu hỗ trợ

### Admin Sidebar

Admin sidebar should only show admin features:

* Bảng quản trị
* Nguồn tri thức
* Tải tài liệu
* Câu hỏi chưa trả lời
* Phân tích

Keep existing login and role guard behavior if already implemented.

If role guard is not implemented yet, add a simple frontend role guard:

* Unauthenticated users go to `/login`
* Student cannot access `/admin/*`
* Admin cannot see student sidebar by default
* Unauthorized access goes to `/403`

---

## 9. Backend Integration

Before creating mock data, inspect the backend/API layer.

Use existing endpoints if they exist.

### Look for Existing APIs For

* Chatbot ask/query
* Student schedule
* Notifications
* Support tickets
* Knowledge sources
* Unanswered questions

### If Endpoints Exist

* Wire the UI to real endpoints.
* Add loading, error, empty, and success states.

### If Endpoints Do Not Exist

Create a clean frontend API adapter layer, for example:

```ts
src/lib/api.ts
```

Or the equivalent location in this repo.

Use fallback demo data only through this adapter.

Add TODO comments documenting the expected backend contract.

### Expected API Functions If Missing

```ts
askVinnie(payload)
getStudentSchedule()
getStudentNotifications()
markNotificationRead(notificationId)
archiveNotification(notificationId)
deleteNotification(notificationId)
getSupportTickets(filters)
getSupportTicketDetail(ticketId)
archiveSupportTicket(ticketId)
deleteSupportTicket(ticketId)
restoreSupportTicket(ticketId)
```

---

## 10. Design Requirements

Keep the app visually consistent with the current VinUni Student Copilot style:

* Premium university SaaS look
* Clean white background
* Deep navy sidebar
* VinUni-inspired red accents
* Rounded cards
* Clear typography
* Professional spacing
* Responsive layout
* Avoid childish chatbot UI

---

## 11. Implementation Quality

Please:

* Reuse existing components where possible.
* Create reusable components where useful.

### Suggested Reusable Components

* `CalendarView`
* `CalendarEventCard`
* `EventDetailDrawer`
* `NotificationList`
* `NotificationFilters`
* `TicketFilters`
* `TicketList`
* `TicketDetailDrawer`
* `ChatCitationList`
* `SourceDrawer`

### Code Quality Requirements

* Do not break the current chatbot flow.
* Do not remove admin pages unless explicitly required.
* Run lint/build/test commands if available.
* Fix any errors caused by the changes.

---

## 12. Add Global Floating Vinnie Chat Bubble

Please keep the existing **“Vinnie” / “Hỏi AI”** sidebar menu, but also add a global floating chat bubble.

### Important UX Decision

Do **not** remove the dedicated Vinnie chat page.

The product should support two ways to access the same assistant:

---

### 12.1 Full Vinnie Page

Accessed from the sidebar menu:

* “Hỏi AI”
* Or “Vinnie”

Used for:

* Deep Q&A
* Source review
* Longer conversations
* Full-width chat experience

This page can show a larger chat layout and source drawer.

---

### 12.2 Floating Vinnie Chat Bubble

The floating Vinnie chat bubble should:

* Always be available in the bottom-right corner across student pages.
* Be used for quick questions without leaving the current page.
* Open as a compact chat widget or slide-up panel.
* Work on:

  * Dashboard
  * Calendar
  * Notifications
  * Support Tickets
  * Other student pages

---

### Shared Chat Behavior

The full Vinnie page and floating chat widget must share the same conversation state.

Requirements:

* If the user asks something in the floating chat, it should also appear when opening the full Vinnie page.
* If the user asks something in the full Vinnie page, it should also appear in the floating chat.
* Conversation should survive route changes.
* Do not reset chat when navigating between pages.

---

### Implementation Suggestion

Move chat state into a global provider mounted at the app/student layout level or app root layout level.

Create or update:

* `ChatProvider`
* `useChat` hook if needed
* `FloatingVinnieButton`
* `VinnieChatWidget`
* `VinnieFullChatPage`
* `ChatMessageList`
* `ChatCitationList`
* `SourceDrawer`

Reuse the same:

* Message list
* Send-message logic
* Citation rendering
* Source drawer logic

in both the widget and full page.

---

### Floating Bubble Requirements

* Position: bottom-right.
* Show Vinnie avatar/icon.
* Tooltip: “Ask Vinnie”.
* Optional unread badge.
* Smooth open/close animation.
* Compact chat panel width around `380–450px` on desktop.
* On mobile, open as a full-screen bottom sheet or full-screen drawer.
* Include minimize/close button.
* Keep input simple.
* Show citations under each assistant answer.
* Clicking **“Nguồn”** or a citation opens the source drawer for that exact answer.

---

### Full Vinnie Page Requirements

Keep the existing sidebar navigation item.

Rename menu item to either **“Vinnie”** or **“Hỏi AI”** consistently.

The full page should provide a richer experience than the floating widget:

* Larger chat area
* Suggested prompts
* Better citation visibility
* Source drawer
* Conversation history

The source panel should still be hidden by default and only open when the user clicks **“Nguồn”** or a citation.

---

### Avoid

* Do not create two separate conversations.
* Do not duplicate chatbot API logic.
* Do not make the bubble visible on the login page.
* Do not make the source panel permanently visible.
* Do not remove role-based separation between Student and Admin.

---

# Acceptance Criteria

The implementation is complete when:

* Student sidebar no longer contains **“Học phí”**.
* Student sidebar has **“Thông báo”**.
* Calendar page looks like a real calendar, not just a plain list.
* Chat mode toggle is removed.
* Right source panel is hidden by default.
* Clicking **“Nguồn”** or a citation opens the source panel.
* Citations appear directly under each assistant answer.
* Tickets can be filtered, hidden/archived, restored, and deleted/removed.
* Login and role-based separation still work.
* Sidebar still has **“Vinnie” / “Hỏi AI”**.
* Floating Vinnie bubble appears across student pages.
* Chat state is shared between sidebar full page and floating widget.
* Chat state survives route changes.
* Source drawer opens only when clicking **“Nguồn”** or a citation.
* App builds successfully.

---

# Final Summary Required

At the end, summarize:

1. Files changed
2. New components added
3. Routes/pages updated
4. Backend endpoints connected
5. Parts still using fallback/demo data
6. How to test the calendar, notifications, tickets, floating chat bubble, and source drawer behavior
