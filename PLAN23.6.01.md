# Ticket Redesign Plan

## 1. Core Direction

Use the ticket template style as the main design direction for both **Student/User** and **Admin**.

### Design Style

* Clean white background
* Large filter panel at the top
* Tickets grouped by status
* Card-based ticket layout
* Clear priority and status badges
* Created / updated date metadata
* Warning icon for urgent or overdue tickets

The same design system should be reused across both roles, but each role has different actions and information hierarchy.

---

# 2. Shared Ticket Layout

## Page Structure

```txt
Ticket Page
├── Header
│   ├── Page title
│   ├── Short description
│   └── Main action button
│
├── Filters Panel
│   ├── Status filter
│   ├── Priority filter
│   ├── Category filter
│   ├── Search input
│   └── Sort dropdown
│
├── Ticket Board
│   ├── Open Tickets
│   ├── In Progress
│   ├── Waiting / Pending
│   └── Closed Tickets
│
└── Ticket Detail Drawer / Modal
```

---

# 3. Ticket Card Design

Each ticket card should include:

```txt
Ticket Card
├── Ticket ID
├── Priority badge
├── Status badge
├── Warning / SLA icon if needed
├── Ticket title
├── Category
├── Created date
├── Updated date
└── Quick action / View detail
```

## Example Card Content

```txt
tk13   medium   open
Login issues with SSO
Technical
Created: 10/30/2025   Updated: 10/30/2025
```

## Badge Style

| Type            | Style                                   |
| --------------- | --------------------------------------- |
| High Priority   | Red border / light red background       |
| Medium Priority | Yellow border / light yellow background |
| Low Priority    | Green border / light green background   |
| Open            | Green / neutral                         |
| In Progress     | Yellow / orange                         |
| Waiting         | Blue / purple                           |
| Closed          | Gray                                    |

---

# 4. Student/User Ticket Page

## Main Goal

The student/user should be able to:

* View their own tickets
* Create a new ticket
* Track ticket status
* Add comments or attachments
* Close or reopen ticket if needed

## User Header

```txt
My Support Tickets
Track your requests and responses from VinUni support teams.

[+ Create New Ticket]
```

## User Filters

Keep the student filters simple:

```txt
Status
Priority
Category
Search by title or ticket ID
```

## User Board Columns

```txt
Open Tickets
In Progress
Waiting for Response
Closed Tickets
```

---

# 5. Create New Ticket Flow

When the user clicks **Create New Ticket**, open a modal or full-page form.

## Form Fields

```txt
Title
Category
Priority
Description
Attachment upload
Related service / department
```

## Recommended Categories

```txt
Academic
Technical
Finance / Tuition
Dormitory
Scholarship
Schedule / Exam
Student Service
Other
```

## Submit Flow

```txt
1. User fills ticket form
2. User clicks Continue / Review
3. Show preview of ticket information
4. User confirms Submit
5. Ticket appears in Open Tickets
```

Important: the ticket should **not be sent directly to admin immediately**.
The user should review the ticket information first, then confirm submission.

---

# 6. Admin Ticket Page

## Main Goal

The admin should be able to:

* View all tickets
* Filter tickets by status, priority, category, assignee, department, and date
* Assign tickets to staff
* Change ticket status
* Reply to students
* Add internal notes
* Track urgent or overdue tickets

## Admin Header

```txt
Ticket Management
Manage student support requests across departments.

[Export] [Refresh]
```

Optional actions:

```txt
[Bulk Assign] [SLA View]
```

## Admin Filters

Admin needs more advanced filters:

```txt
Status
Priority
Category
Assignee
Department
Date range
Search by student / title / ticket ID
```

## Admin Board Columns

```txt
Open Tickets
In Progress
Waiting for Student
Resolved / Closed
```

## Admin Ticket Card Extra Info

Admin cards should include more operational information:

```txt
Ticket ID
Priority
Status
Student name
Category
Assigned admin
Created date
Updated date
SLA warning
```

## Example Admin Card

```txt
tk13   medium   open
Login issues with SSO
Student: Nguyen Van A
Category: Technical
Assigned: IT Support
Created: 10/30/2025   Updated: 10/30/2025
```

---

# 7. Ticket Detail View

Use a right-side drawer or modal when clicking a ticket.

## Student Detail View

```txt
Ticket title
Status
Priority
Category
Description
Attachments
Admin replies
Conversation history
Add comment
Close ticket
```

## Admin Detail View

```txt
Ticket title
Student information
Status
Priority
Category
Description
Attachments
Conversation history
Internal notes
Assign admin
Change status
Reply to student
Close ticket
```

---

# 8. User vs Admin Difference

| Feature               | Student/User     | Admin       |
| --------------------- | ---------------- | ----------- |
| View tickets          | Own tickets only | All tickets |
| Create ticket         | Yes              | Optional    |
| Change status         | Limited          | Full        |
| Assign ticket         | No               | Yes         |
| Add internal note     | No               | Yes         |
| Reply                 | Yes              | Yes         |
| Filter by assignee    | No               | Yes         |
| SLA / overdue warning | View only        | Manage      |
| Export tickets        | No               | Yes         |

---

# 9. Component Plan

```txt
components/tickets/
├── TicketPageHeader.tsx
├── TicketFilters.tsx
├── TicketBoard.tsx
├── TicketColumn.tsx
├── TicketCard.tsx
├── TicketDetailDrawer.tsx
├── CreateTicketModal.tsx
├── TicketBadge.tsx
└── TicketEmptyState.tsx
```

## Role-Based Rendering

```tsx
<TicketBoard role="student" />
<TicketBoard role="admin" />
```

Or:

```tsx
const isAdmin = user.role === "admin";
```

Then conditionally show admin-only controls.

---

# 10. UI Improvements

## Improvements Compared to Current Template

1. Add a clear page header with main action.
2. Add search input inside the filter panel.
3. Reduce ticket card height slightly for better scanning.
4. Add hover state to ticket cards.
5. Make warning icon meaningful: urgent, overdue, or no response.
6. Use drawer for ticket detail instead of navigating away.
7. Use consistent badge colors.
8. On mobile, change board columns into vertical sections.
9. Add empty state for each ticket status section.
10. Add loading skeleton when fetching tickets.

---

# 11. Final Design Direction

## Student Side

Simple, personal, and action-focused.

Main action:

```txt
Create New Ticket
```

## Admin Side

Operational, filter-heavy, and management-focused.

Main actions:

```txt
Manage
Assign
Resolve
Reply
Export
```

## Overall Goal

The ticket UI should feel like a lightweight support dashboard:

* Clean cards
* Clear statuses
* Fast filtering
* Easy ticket creation
* Easy ticket detail management
* Consistent experience between student and admin

# Streaming Text Feature Plan  
## VinUni Student Copilot — Vinnie Chatbot

## 1. Goal

Implement real-time streaming text for Vinnie so users can see answers appear progressively instead of waiting for the full response.

Chosen approach:

> Backend Proxy + Fetch Streaming / ReadableStream

The frontend sends a request to the backend.  
The backend handles auth, permissions, RAG, personal data checks, LLM streaming, and streams structured events back to the frontend.

---

## 2. Current Project Structure

Current structure:

```txt
frontend/
  .next/
  app/
  components/
  lib/
  node_modules/
  .dockerignore
  .feedback.json
  .gitignore
  Dockerfile
  next-env.d.ts
  next.config.js
  package-lock.json
  package.json
  README.md
  tsconfig.json
  tsconfig.tsbuildinfo

frontend_backup_20260618/
LOGS/
scripts/
tests/
vinchatbot/
vinchatbot.egg-info/
.dockerignore
.env
```

Important note:

```txt
This project does not use /src.
All new frontend files should be placed directly inside:
- frontend/app
- frontend/components
- frontend/lib
```

---

## 3. Recommended Architecture

```txt
User sends message
→ Frontend calls /api/chat/stream
→ Next.js API route receives request
→ Backend validates user session
→ Backend checks role and permission
→ Backend detects chat mode
→ Backend retrieves official VinUni documents or personal data
→ Backend calls LLM with streaming
→ Backend streams structured events to frontend
→ Frontend renders text progressively
→ Final answer and citations are saved to database
```

---

## 4. Suggested Folder Structure

Use this structure inside the existing `frontend` folder:

```txt
frontend/
  app/
    api/
      chat/
        stream/
          route.ts

    student/
      layout.tsx
      page.tsx

  components/
    chat/
      ChatBox.tsx
      ChatMessage.tsx
      ChatInput.tsx
      StreamingStatus.tsx
      CitationList.tsx
      SuggestedQuestions.tsx
      StopGeneratingButton.tsx

  lib/
    chat/
      stream-client.ts
      stream-parser.ts
      chat-types.ts
      message-utils.ts

    server/
      chat/
        build-prompt.ts
        check-permission.ts
        retrieve-sources.ts
        stream-chat.ts
        save-conversation.ts
        generate-title.ts
```

Do not create:

```txt
src/
```

Use:

```txt
frontend/app
frontend/components
frontend/lib
```

---

## 5. Streaming API Endpoint

Create this endpoint:

```txt
frontend/app/api/chat/stream/route.ts
```

Endpoint:

```txt
POST /api/chat/stream
```

Request body:

```ts
{
  conversationId?: string;
  message: string;
  mode: "general" | "personal" | "ticket" | "schedule";
}
```

Response type:

```txt
Content-Type: text/event-stream
```

---

## 6. Stream Event Design

Do not stream only raw text.  
Use structured events so the frontend can understand what is happening.

Create:

```txt
frontend/lib/chat/chat-types.ts
```

Suggested types:

```ts
export type ChatMode =
  | "general"
  | "personal"
  | "ticket"
  | "schedule";

export type StreamEvent =
  | {
      type: "status";
      step:
        | "checking"
        | "retrieving"
        | "verifying"
        | "generating"
        | "saving";
      message: string;
    }
  | {
      type: "delta";
      text: string;
    }
  | {
      type: "citation";
      sourceTitle: string;
      sourceUrl?: string;
      chunkId?: string;
    }
  | {
      type: "suggestions";
      questions: string[];
    }
  | {
      type: "error";
      message: string;
    }
  | {
      type: "done";
      messageId: string;
      conversationId: string;
    };
```

---

## 7. Example Streaming Flow

Example for a RAG question:

```txt
User asks:
"What is the final exam policy?"

Backend streams:

status: Checking your request...
status: Searching official VinUni sources...
status: Verifying relevant documents...
status: Generating verified answer...
delta: According to the official VinUni policy...
delta: students should...
citation: VinUni Academic Handbook
suggestions: ["When is the exam schedule?", "Who should I contact?"]
done: messageId
```

Frontend behavior:

```txt
1. Show user message immediately
2. Create empty Vinnie message
3. Show current status
4. Append delta text progressively
5. Show citations after answer
6. Show suggested questions at the end
7. Mark message as done
```

---

## 8. Backend Responsibilities

The backend API route should handle:

```txt
1. Authenticate current user
2. Validate request body
3. Check user role
4. Check permissions based on chat mode
5. Retrieve official VinUni sources when needed
6. Retrieve personal student data only when allowed
7. Build prompt
8. Call LLM with streaming enabled
9. Convert LLM output into stream events
10. Save final conversation result
11. Return done event
```

---

## 9. RAG Streaming Rule

For official VinUni answers, do not start streaming the final answer immediately.

Recommended order:

```txt
1. Stream status: "Searching official VinUni sources..."
2. Retrieve relevant documents
3. Validate source relevance
4. Build answer only from relevant sources
5. Stream final answer
6. Attach only used citations
```

Important rule:

```txt
Never show citations that were not actually used to generate the answer.
```

This avoids the issue where Vinnie gives irrelevant citations.

---

## 10. Personal Mode Rule

For personal student data, such as:

```txt
- GPA
- tuition balance
- schedule
- ticket status
- academic status
- personal deadlines
```

The backend must check permission before retrieving or streaming anything.

Rules:

```txt
- Never stream personal data before auth and permission checks
- Never expose raw database records directly in stream events
- Avoid saving sensitive personal information unnecessarily
- Avoid storing personal-mode messages in localStorage
- Prefer database persistence with proper access control
```

---

## 11. Chat State Location

Current problem:

```txt
If chat state lives only inside page.tsx,
it may reset when navigating between student tabs.
```

Recommended solution:

```txt
frontend/app/student/layout.tsx
→ wraps student pages with ChatProvider
```

Create:

```txt
frontend/components/chat/ChatProvider.tsx
```

or:

```txt
frontend/lib/chat/chat-provider.tsx
```

Recommended:

```txt
frontend/components/chat/ChatProvider.tsx
```

Because it is a React provider component.

Expected behavior:

```txt
- Chat survives navigation between student pages
- Current streaming request does not disappear immediately
- Conversation state is shared across student routes
```

---

## 12. Frontend Streaming Client

Create:

```txt
frontend/lib/chat/stream-client.ts
```

Responsibilities:

```txt
- Send POST request to /api/chat/stream
- Create AbortController
- Read response.body stream
- Pass chunks to stream parser
- Update UI with parsed events
- Handle stop generating
- Handle network errors
```

High-level flow:

```txt
sendMessage()
→ add user message
→ add empty assistant message
→ start fetch stream
→ read chunks
→ parse events
→ update assistant message
→ finish or error
```

---

## 13. Stream Parser

Create:

```txt
frontend/lib/chat/stream-parser.ts
```

Responsibilities:

```txt
- Receive raw text chunks
- Buffer incomplete chunks
- Parse structured events
- Return valid StreamEvent objects
- Ignore malformed partial chunks until complete
```

The parser should handle cases where JSON is split across chunks.

Example problem:

```txt
Chunk 1:
{"type":"delta","text":"Hello

Chunk 2:
 world"}
```

Parser must combine them before parsing.

---

## 14. Chat UI Components

Create or update these components:

```txt
frontend/components/chat/ChatBox.tsx
frontend/components/chat/ChatMessage.tsx
frontend/components/chat/ChatInput.tsx
frontend/components/chat/StreamingStatus.tsx
frontend/components/chat/CitationList.tsx
frontend/components/chat/SuggestedQuestions.tsx
frontend/components/chat/StopGeneratingButton.tsx
```

Component responsibilities:

```txt
ChatBox.tsx
- Main chat container
- Holds message list
- Connects input and streaming logic

ChatMessage.tsx
- Renders user and assistant messages
- Shows streaming state
- Shows final answer

ChatInput.tsx
- User input
- Submit button
- Disable while needed

StreamingStatus.tsx
- Shows status such as:
  "Searching official VinUni sources..."
  "Generating verified answer..."

CitationList.tsx
- Shows verified source cards
- Only displays citations returned by backend

SuggestedQuestions.tsx
- Shows follow-up questions after the answer is done

StopGeneratingButton.tsx
- Allows user to stop the current stream
```

---

## 15. Message Status Design

Each assistant message should have a status.

```ts
export type MessageStatus =
  | "pending"
  | "retrieving"
  | "streaming"
  | "done"
  | "error"
  | "stopped";
```

Example:

```ts
export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode?: ChatMode;
  status?: MessageStatus;
  citations?: Citation[];
  suggestions?: string[];
  createdAt: string;
};
```

---

## 16. Stop Generating Behavior

Use `AbortController`.

Flow:

```txt
User clicks "Stop generating"
→ Frontend aborts fetch request
→ Backend stops stream if possible
→ Assistant message status becomes "stopped"
→ UI shows "Regenerate" option
```

UI behavior:

```txt
While streaming:
- Show "Stop generating"

After stopped:
- Show "Stopped"
- Show "Regenerate"
```

---

## 17. Save Conversation Behavior

Recommended behavior:

```txt
1. Save user message when request starts
2. Save assistant message after stream completes
3. Save citations after final answer is generated
4. Save message status as done, error, or stopped
```

Suggested database structure:

```txt
conversations
- id
- user_id
- title
- created_at
- updated_at

messages
- id
- conversation_id
- role
- content
- mode
- status
- created_at

message_sources
- id
- message_id
- source_title
- source_url
- chunk_id
- created_at
```

---

## 18. Error Handling

Handle these errors:

```txt
- User not authenticated
- User does not have permission
- Invalid request body
- RAG source not found
- Weak source relevance
- LLM timeout
- Stream disconnected
- User manually stopped generation
- Backend internal error
```

Frontend messages should be friendly.

Examples:

```txt
"I could not find a reliable official VinUni source for this answer."

"Your session expired. Please sign in again."

"You do not have permission to access this information."

"Vinnie stopped generating this response."
```

---

## 19. Recommended UX

Bad UX:

```txt
Embedding search running...
Similarity threshold failed...
Tool call returned empty result...
```

Good UX:

```txt
Searching official VinUni sources...
Checking relevant student information...
Generating verified answer...
```

The user should see simple, human-readable statuses.

---

## 20. Implementation Phases

## Phase 1 — Basic Streaming

Goal:

```txt
Make Vinnie stream plain text from backend to frontend.
```

Tasks:

```txt
- Create frontend/app/api/chat/stream/route.ts
- Implement basic streaming response
- Implement frontend fetch streaming
- Append streamed text into assistant message
- Add loading and done states
```

---

## Phase 2 — Structured Stream Events

Goal:

```txt
Support status, delta, error, and done events.
```

Tasks:

```txt
- Create frontend/lib/chat/chat-types.ts
- Create frontend/lib/chat/stream-parser.ts
- Create frontend/lib/chat/stream-client.ts
- Add status event handling
- Add delta event handling
- Add error event handling
- Add done event handling
```

---

## Phase 3 — RAG Integration

Goal:

```txt
Stream verified answers based on official VinUni sources.
```

Tasks:

```txt
- Add source retrieval before generation
- Stream "Searching official VinUni sources..."
- Validate source relevance
- Generate answer only from retrieved context
- Return citations only from used sources
```

---

## Phase 4 — Personal Mode

Goal:

```txt
Safely stream answers that use student-specific data.
```

Tasks:

```txt
- Add permission checks
- Add RBAC/ABAC validation
- Prevent unauthorized personal data access
- Avoid localStorage persistence for sensitive content
- Add audit logging if needed
```

---

## Phase 5 — Chat Persistence

Goal:

```txt
Save conversations and support chat history.
```

Tasks:

```txt
- Save user messages
- Save assistant messages
- Save citations
- Add conversation history sidebar or chat history panel
- Add new conversation button
- Auto-generate conversation title
```

---

## Phase 6 — UX Polish

Goal:

```txt
Make streaming feel smooth and reliable.
```

Tasks:

```txt
- Add Stop Generating button
- Add Regenerate button
- Add typing animation
- Add source cards
- Add suggested follow-up questions
- Add retry on stream error
```

---

## Phase 7 — Reliability and Security

Goal:

```txt
Make streaming production-ready.
```

Tasks:

```txt
- Add rate limiting
- Add request timeout
- Add backend logging
- Add error monitoring
- Add permission audit
- Add protection against prompt injection
- Add source relevance threshold
```

---

## 21. Final Recommended File Checklist

Create these files:

```txt
frontend/app/api/chat/stream/route.ts

frontend/components/chat/ChatBox.tsx
frontend/components/chat/ChatMessage.tsx
frontend/components/chat/ChatInput.tsx
frontend/components/chat/StreamingStatus.tsx
frontend/components/chat/CitationList.tsx
frontend/components/chat/SuggestedQuestions.tsx
frontend/components/chat/StopGeneratingButton.tsx

frontend/lib/chat/chat-types.ts
frontend/lib/chat/stream-client.ts
frontend/lib/chat/stream-parser.ts
frontend/lib/chat/message-utils.ts

frontend/lib/server/chat/build-prompt.ts
frontend/lib/server/chat/check-permission.ts
frontend/lib/server/chat/retrieve-sources.ts
frontend/lib/server/chat/stream-chat.ts
frontend/lib/server/chat/save-conversation.ts
frontend/lib/server/chat/generate-title.ts
```

---

## 22. Final Flow

```txt
User sends message
→ ChatInput submits message
→ ChatBox adds user message
→ ChatBox creates empty assistant message
→ stream-client calls /api/chat/stream
→ route.ts checks auth and permission
→ retrieve-sources.ts gets official VinUni context
→ build-prompt.ts builds final prompt
→ stream-chat.ts streams LLM output
→ frontend receives status and delta events
→ ChatMessage renders answer progressively
→ CitationList renders verified sources
→ SuggestedQuestions renders follow-up questions
→ save-conversation.ts saves final result
→ done event completes the message
```

---

## 23. Priority Summary

| Priority | Task |
|---|---|
| High | Create `/api/chat/stream` endpoint |
| High | Implement frontend `ReadableStream` client |
| High | Add `status`, `delta`, `error`, `done` events |
| High | Retrieve RAG sources before answer streaming |
| High | Prevent irrelevant citations |
| High | Move chat state into provider under `app/student/layout.tsx` |
| Medium | Add Stop Generating button |
| Medium | Save chat history |
| Medium | Add source cards |
| Medium | Add suggested follow-up questions |
| Low | Add Regenerate button |
| Low | Add auto conversation title |
| Low | Add advanced retry behavior |

---

## 24. Main Principle

The streaming feature should not just make text appear faster.

It should make Vinnie feel:

```txt
- faster
- more transparent
- more trustworthy
- safer with student data
- better at showing verified sources
```

Final recommended implementation:

```txt
Backend Proxy + Fetch Streaming / ReadableStream
with structured stream events:
status → delta → citation → suggestions → done
```