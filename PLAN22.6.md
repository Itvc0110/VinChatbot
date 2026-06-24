# VinUni Student Copilot — Implementation Planning Prompt

You are working in this repo:

```bash
/home/dholmes/AIInAction/Project/VinChatbot
```

Please inspect the existing project structure first, then create a detailed implementation plan.

**Do not write code yet.**
I want a practical, repo-aware plan for improving the VinUni Student Copilot web app based on the product changes below.

---

## 1. Project Context

This is a **VinUni Student Copilot** web app.

The chatbot is named **Vinnie**.

The app supports students with:

* Verified answers from official VinUni sources
* Notifications
* Schedules
* Policies
* Support tickets
* Admin console

The app should not behave like a simple chatbot. It should feel like a proactive student support platform where:

* Students receive official notifications from the university
* Vinnie suggests timely questions based on those notifications
* Vinnie gives verified answers with sources
* Vinnie can prepare support ticket drafts
* Students must review and confirm ticket details before anything is sent to admin
* Admins can manage notifications, tickets, and support workflows

---

# 2. Main Product Changes to Plan

## A. Notification-to-Question Engine

The notification center is where the university sends announcements to students, such as:

* Class schedules
* Exam schedules
* Scholarship deadlines
* Tuition deadlines
* Event announcements
* Academic policy updates
* Wellbeing, career, or exchange announcements

The system should analyze notifications and generate or display suggested questions for Vinnie based on:

* Notification category
* Event date
* Deadline
* Current date
* Target audience
* Priority
* Related student context, if available
* Popular questions asked by other students, if supported later

---

## Example: Exam Period

If it is exam period, Vinnie should show suggested questions like:

* When is my final exam schedule?
* Where is my exam room?
* What should I bring to the exam?
* What happens if I miss an exam?
* What are the exam regulations?

---

## Example: Scholarship Deadline

If a scholarship deadline is approaching, Vinnie should show suggested questions like:

* Am I eligible for this scholarship?
* What documents do I need?
* How do I apply?
* Who should I contact?
* Can I still submit after the deadline?

---

## Time-aware Suggested Questions

The suggested questions should be time-aware:

### If a deadline is far away

Suggest general discovery questions.

Example:

* What is this scholarship about?
* Am I eligible?
* What are the main requirements?

### If a deadline is near

Suggest action-oriented questions.

Example:

* What documents do I still need?
* How do I submit before the deadline?
* Who should I contact if I have an issue?

### If a deadline has passed

Suggest late-submission or contact-office questions.

Example:

* Can I still submit late?
* Who should I contact?
* What should I do if I missed the deadline?

---

## MVP Direction

For MVP, this can be rule-based using notification categories and templates.

Later, it can be upgraded with:

* AI-generated prompts
* Question trend analysis
* Personalized suggestions
* Student-context-aware ranking

---

## Please Plan for Notification-to-Question Engine

Please include:

* Data model changes
* UI changes
* API changes
* Where this logic should live
* How to rank suggested questions
* How to display them in the Vinnie chat page
* How to display them in the notification page
* How admin should create or approve suggested questions

---

# 3. Smart Ticket Draft & Routing

Currently, the app can send requests to admin.

I want to change the flow.

## Important Change

Vinnie must **not** automatically create and send a ticket to admin.

Instead, the correct flow should be:

1. Student describes an issue to Vinnie.
2. Vinnie detects that the issue may require staff support.
3. Vinnie prepares a pre-filled support ticket draft.
4. The student sees a **Review Ticket** panel, modal, or drawer.
5. The student can review and edit the ticket fields.
6. The student clicks **Send to Admin**.
7. Only after user confirmation is the ticket submitted to admin.
8. Admin only sees submitted tickets, not unconfirmed drafts.

---

## Review Ticket UI

The Review Ticket UI should include:

* Category
* Assigned office
* Priority
* Summary
* Description
* Related conversation context
* Checkbox: include relevant chat context
* Attachments, if the current app supports them or can support them later
* Buttons:

  * Cancel
  * Save Draft
  * Send to Admin

---

## Suggested Wording

Use this wording:

> Vinnie prepared a support ticket draft. Please review it before sending.

Do **not** use wording like:

> Vinnie created a ticket for you.

Because the ticket should not be considered created/submitted until the user confirms.

---

## Ticket Statuses

Ticket statuses should support:

* `draft`
* `submitted`
* `in_review`
* `waiting_for_student`
* `resolved`
* `closed`

Admin should only see tickets where:

```ts
status !== "draft"
confirmed_by_user === true
```

Or more strictly:

```ts
status === "submitted" || status === "in_review" || status === "waiting_for_student" || status === "resolved" || status === "closed"
```

---

## Please Plan for Smart Ticket Draft & Routing

Please include:

* How to change the current ticket flow
* How to represent ticket drafts
* Whether draft tickets should be stored in the database or temporarily in frontend state
* Which option is better for MVP
* Data model changes
* API endpoint changes
* UI component changes
* Admin dashboard filtering changes
* Security and privacy considerations

---

# 4. Privacy and PII

The app may handle sensitive student data such as:

* GPA
* Tuition
* Scholarship status
* Personal schedule
* Ticket history
* Academic issues
* Financial aid questions

The plan should avoid sending the entire chat history to admin by default.

Instead:

* Include only a short relevant summary by default
* Let the student choose whether to include relevant chat context
* Never submit private chat context without user confirmation

---

## Please Plan for Privacy and PII

Please include:

* How to avoid leaking unnecessary personal data
* What should be included in a ticket by default
* What should require user confirmation
* Whether `localStorage` or `sessionStorage` should be avoided for sensitive ticket/chat data
* How backend RBAC should protect ticket visibility

---

# 5. Verified Answer + Action Drawer

Vinnie answers should ideally support:

* Short answer
* Detailed explanation
* Confidence level
* Official source or citation
* Related policy
* Suggested next actions

Suggested actions may include:

* Review Ticket
* Open related policy
* Set reminder
* Ask follow-up
* Contact office

---

## Expected Flow

Example flow:

```text
Vinnie answer
→ Suggested action: Prepare Support Ticket
→ Review Ticket panel
→ Student reviews and edits
→ Student confirms
→ Ticket submitted to admin
```

Please plan how this interacts with the ticket draft flow.

---

# 6. Admin Console

Admin should support:

* Viewing submitted tickets
* Updating ticket status
* Responding to tickets
* Creating notifications
* Selecting notification category, target audience, event date, deadline, and priority
* Reviewing or editing suggested questions generated from notifications
* Publishing notifications with approved suggested questions

---

## Please Plan for Admin Console

Please include:

* Admin pages/components to add or modify
* Ticket table filters
* Notification creation form
* Suggested question approval UI
* Role-based access assumptions

---

# 7. MVP vs Later Phases

Please split the plan into clear phases.

---

## MVP

The MVP should include:

* Rule-based notification suggested questions
* Review Ticket draft flow
* Admin sees only confirmed submitted tickets
* Basic ticket status lifecycle
* Notification page
* Suggested prompts in Vinnie
* Basic admin notification creation
* Basic suggested question approval or editing

---

## Phase 2

Phase 2 may include:

* Time-aware ranking
* AI-generated suggested questions
* Question trend analysis from other students
* Personalized student context
* Stronger RBAC/ABAC
* Audit logs
* Better ticket workflow

---

## Phase 3

Phase 3 may include:

* Human-in-the-loop knowledge review
* Analytics dashboard
* Advanced notification personalization
* Event recommender
* Calendar integration
* Department-level admin console
* Mobile/PWA improvements

---

# 8. Required Output Format

Please provide a clear implementation plan with these sections:

## 1. Current Repo Observations

Explain the current project structure, framework, routing style, major folders, and relevant existing patterns.

## 2. Existing Relevant Files, Components, and Routes

List the files likely related to:

* Chat page
* Notifications
* Tickets
* Admin console
* API routes
* Data models
* Shared UI components
* State management

## 3. Proposed Architecture

Explain the proposed feature architecture without replacing the existing app architecture unnecessarily.

## 4. Data Model Changes

Include proposed fields for:

### `notifications`

```ts
{
  id: string
  title: string
  content: string
  category: string
  targetAudience: string[]
  startDate?: Date
  endDate?: Date
  deadline?: Date
  eventDate?: Date
  priority: "low" | "medium" | "high" | "urgent"
  status: "draft" | "published" | "archived"
  createdBy: string
  createdAt: Date
  updatedAt: Date
}
```

### `suggested_questions`

```ts
{
  id: string
  notificationId: string
  questionText: string
  category: string
  triggerPhase: "early" | "near_deadline" | "overdue" | "active"
  score: number
  createdByAi: boolean
  approvedByAdmin: boolean
  isActive: boolean
  createdAt: Date
  updatedAt: Date
}
```

### `tickets`

```ts
{
  id: string
  studentId: string
  category: string
  assignedOffice: string
  priority: "low" | "medium" | "high" | "urgent"
  summary: string
  description: string
  status: "draft" | "submitted" | "in_review" | "waiting_for_student" | "resolved" | "closed"
  sourceConversationId?: string
  includedContext?: string
  includeChatContext: boolean
  createdByAi: boolean
  confirmedByUser: boolean
  submittedAt?: Date
  createdAt: Date
  updatedAt: Date
}
```

Adjust field names to match the repo conventions.

## 5. API Changes

Plan endpoints or server actions for:

* Creating notification
* Updating notification
* Publishing notification
* Generating suggested questions
* Approving suggested questions
* Fetching active suggested questions for a student
* Preparing a ticket draft
* Saving a ticket draft
* Submitting a ticket
* Updating ticket status as admin
* Fetching tickets with admin filters

## 6. Frontend UI Changes

Plan changes for:

* Vinnie chat page
* Suggested prompt cards
* Notification center
* Review Ticket modal/drawer
* Verified answer card
* Action drawer

## 7. Admin Console Changes

Plan changes for:

* Notification creation page
* Suggested question review UI
* Submitted ticket table
* Ticket detail view
* Ticket status updates
* Filtering out draft/unconfirmed tickets

## 8. Ticket Draft Flow

Explain the exact user flow and state transitions:

```text
conversation issue detected
→ prepare ticket draft
→ open review UI
→ user edits
→ save draft or submit
→ admin receives only submitted ticket
```

## 9. Notification-to-Question Flow

Explain the exact flow:

```text
admin creates notification
→ category/deadline/event date selected
→ system generates template questions
→ admin reviews/edits questions
→ notification published
→ student sees notification
→ Vinnie shows timely suggested questions
```

## 10. Privacy and Security Considerations

Include:

* No automatic submission of full chat history
* Only relevant summarized context by default
* User confirmation before sending
* Avoid storing sensitive data in localStorage
* Backend authorization for ticket visibility
* Role-based access for admin/offices
* Audit log suggestion for later phase

## 11. MVP Implementation Steps

Break the MVP into practical steps in the right order.

For example:

1. Inspect current routes/components/models
2. Add or update ticket status model
3. Add Review Ticket UI
4. Change current direct-submit flow into draft-review-submit flow
5. Filter admin tickets
6. Add notification categories
7. Add template-based suggested questions
8. Display suggested questions in Vinnie
9. Add admin notification creation/editing UI
10. Test end-to-end flow

## 12. Phase 2 and Phase 3 Improvements

List improvements after MVP.

## 13. Acceptance Criteria

Include testable criteria, such as:

* Vinnie never submits a ticket automatically
* User must click **Send to Admin** before ticket is visible to admin
* Admin cannot see draft tickets
* Notification with category `exam` produces exam-related suggested questions
* Suggested questions change depending on deadline phase
* User can edit ticket category, priority, summary, and description before submitting
* Chat context is not included unless the user explicitly allows it
* Ticket status updates are visible to the student

## 14. Risks and Tradeoffs

Discuss:

* Storing ticket drafts in DB vs frontend state
* Rule-based prompts vs AI-generated prompts
* Privacy risks of chat context
* Over-notification risk
* Admin workload for approving generated questions
* Complexity of personalized suggestions

## 15. Exact Files Likely to Modify

Based on repo inspection, list the exact files that should likely be modified.

---

# 9. Important Constraints

* Do not implement code yet.
* Do not invent a completely new architecture if the repo already has a structure.
* Use the existing framework, routing style, components, UI library, and styling conventions.
* Prefer simple, feasible MVP implementation over over-engineering.
* If something is unclear, make a reasonable assumption and state it.
* Focus on practical changes that can be implemented in the current project.
* Keep privacy and user confirmation as core design principles.
