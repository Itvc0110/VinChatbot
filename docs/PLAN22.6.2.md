# UI Improvement Plan — VinUni Student Copilot / Ask Vinnie

## Goal

Refine the current Ask Vinnie UI to feel cleaner, more polished, and more usable for students. Keep the existing layout direction: main chat area on the left and source verification panel on the right.

---

## 1. Improve Overall Layout

### Problems

* Current UI feels too crowded.
* Too much information appears at the same time.
* Chat content, citations, source panel, quick questions, and action buttons compete for attention.

### Tasks

* Make spacing more breathable across the chat area and source panel.
* Prevent horizontal overflow from citations or long source text.
* Keep the main chat as the primary focus.
* Allow the source panel to be collapsible.
* On smaller screens, turn the source panel into a right-side drawer.

---

## 2. Improve Chat with Vinnie

### Requirements

Add proper conversation management for the Vinnie chat experience.

### Tasks

* Add a conversation history section/sidebar where users can view previous conversations.
* Allow users to create a new conversation.
* Rename each conversation based on its topic instead of using generic names like `RAG rag`.
* Keep the current conversation state when navigating between student pages.
* The chat should not reset every time the user changes tabs/routes.
* For sensitive student data such as GPA, tuition, or personal schedule, avoid unnecessary long-term persistence.

### Suggested behavior

* Conversation history shows recent chats with short generated titles.
* “New Chat” starts a fresh conversation.
* Clicking an old conversation restores its messages.
* Current active conversation should be visually highlighted.

---

## 3. Simplify the Main Answer Card

### Problems

* Citation text inside the answer is too long and visually noisy.
* The answer looks like a technical prototype instead of a student-facing product.

### Tasks

* Keep the answer text clean and readable.
* Replace long inline citations with compact source chips.
* Example: `Sources: Career Services VN, Career Guidebook, Academic Calendar`
* When a source chip is clicked, highlight the matching source in the right panel.
* Avoid displaying long raw citation text directly inside the message bubble.

---

## 4. Improve Source Panel

### Problems

* Source cards are too long.
* Labels like `unverified` and `Official` shown together are confusing.
* The panel is hard to scan quickly.

### Tasks

* Redesign each source card into a compact format:

  * Source title
  * Source type: `Official Page`, `PDF`, `Policy`, etc.
  * Source status
  * Short excerpt, max 2–3 lines
  * `Open source` action
* Add expand/collapse behavior for long excerpts.
* Highlight the source currently referenced by the answer.
* Make source cards easier to scan visually.

### Label changes

Avoid confusing combinations like:

`unverified` + `Official`

Use clearer labels instead:

* `Official source`
* `Source verified`
* `Answer confidence: Low`
* `Needs confirmation`
* `Retrieved from VinUni`

---

## 5. Improve Suggested Questions

### Problems

* Suggested questions are useful but language is inconsistent.
* The UI is in Vietnamese, but suggestions are in English.

### Tasks

* Match suggested question language with the selected UI language.
* In Vietnamese mode, show Vietnamese suggestions.
* In English mode, show English suggestions.
* Suggested questions should be relevant to the current context, such as notifications, exams, deadlines, events, or career fair topics.

### Example Vietnamese suggestions

* `Làm sao để rút học phần trước hạn?`
* `Rút học phần có bị ghi W trên bảng điểm không?`
* `Có những công ty nào tham dự CS Career Fair?`
* `Có cần đăng ký trước cho CS Career Fair không?`

---

## 6. Improve Action Buttons

### Problems

* Too many actions appear at once.
* Some actions appear even when they are not relevant.

### Tasks

* Only show contextual actions when they make sense.
* `Add to calendar` and `Set reminder` should only appear when the answer contains a date, deadline, event, or schedule.
* `Prepare support ticket` should open a review form first, not automatically submit.
* User should review the ticket information before sending it to admin.

### Suggested button hierarchy

Primary:

* `Ask follow-up`

Secondary:

* `Open source`
* `Prepare support ticket`

Contextual:

* `Add to calendar`
* `Set reminder`

---

## 7. Improve Visual Polish

### Tasks

* Reduce overuse of red borders and red highlights.
* Use red mainly for:

  * Vinnie avatar
  * Primary button
  * Active source highlight
* Make inactive elements more neutral.
* Improve text contrast and readability in dark mode.
* Make links, tags, and buttons feel consistent.
* Ensure all scrollbars and dividers feel polished, not like debug UI.

---

## 8. Acceptance Criteria

The final UI should satisfy these points:

* Chat area feels clean and readable.
* Source panel is useful but not overwhelming.
* Long citations no longer break the layout.
* Users can create a new conversation.
* Users can view and reopen previous conversations.
* Conversation titles are based on chat topics.
* Suggested questions match the selected language.
* Action buttons only appear when relevant.
* Support ticket flow requires user review before sending.
* The UI feels like a polished university SaaS product, not a technical prototype.
