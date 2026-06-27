"use client";

// Portal chrome + screen copy, bilingual (EN/VI) so the EN/VI toggle in the top bar
// switches the ENTIRE portal interface — nav, page bodies, tables, forms, toasts and
// the enum badges (status / priority / kind …) — not just the navigation.
//
// Kept separate from the chat i18n dictionary (./i18n) so the existing chat strings stay
// untouched. Both read the same `lang` from the shared LanguageProvider.

import { useI18n, type Lang } from "./i18n";
import type {
  ScheduleDay,
  DeadlineKind,
  TuitionItemStatus,
  TicketStatus,
  TicketPriority,
  TicketCategory,
  NotificationType,
  CalendarEventType,
  SourceStatus,
  SourceCategory,
  QuestionFailureReason,
  QuestionPriority,
  QuestionStatus,
} from "./portalTypes";

export type LogLevel = "info" | "warn" | "error" | "success";

export interface PortalStrings {
  productName: string;
  productNameFull: string;
  productTagline: string;
  studentPortal: string;
  adminPortal: string;

  nav: {
    dashboard: string;
    chat: string;
    schedule: string;
    notifications: string;
    tuition: string;
    tickets: string;
    adminDashboard: string;
    adminTickets: string;
    adminNotifications: string;
    sources: string;
    upload: string;
    questions: string;
    analytics: string;
    logs: string;
  };

  // role + auth chrome
  roleStudent: string;
  roleAdmin: string;
  signOut: string;
  adminConsole: string;
  adminConsoleSub: string;
  adminWarning: string;
  studentChatNote: string;
  authFooter: string;

  login: {
    title: string;
    subtitle: string;
    emailLabel: string;
    passwordLabel: string;
    signIn: string;
    continueStudent: string;
    continueAdmin: string;
    sso: string;
    ssoHint: string;
    securityNote: string;
    demoStudent: string;
    demoAdmin: string;
    or: string;
  };

  access: {
    title: string;
    message: string;
    backToDashboard: string;
    signOut: string;
  };

  // common
  viewAll: string;
  openSource: string;
  loading: string;
  empty: string;
  retry: string;
  errorGeneric: string;
  back: string;
  view: string;
  year: string;
  daysLeft: (n: number) => string;
  dueToday: string;
  overdue: string;

  // chat mode toggle (toggle removed; kept for back-compat with existing strings)
  modeGeneral: string;
  modePersonal: string;
  modeHint: string;
  personalizedAnswer: string;
  chatSuggested: string[];
  somethingWrong: string;
  // full Ask Vinnie page: welcome state + composer trust note
  chatWelcomeTitle: (name: string) => string;
  chatWelcomeSub: string;
  chatTrustNote: string;
  // conversation history (PLAN22.6.2 §2)
  chatHistory: {
    title: string;
    newChat: string;
    untitled: string;
    empty: string;
    rename: string;
    delete: string;
    deleteConfirm: string;
    actions: string;
    save: string;
    cancel: string;
    processing: string;
    stillWaiting: string;
  };

  // notifications screen
  notif: {
    title: string;
    markAllRead: string;
    markRead: string;
    markUnread: string;
    markImportant: string;
    unmarkImportant: string;
    archive: string;
    delete: string;
    deleteConfirm: string;
    confirmDelete: string;
    cancel: string;
    unreadCount: (n: number) => string;
    emptyTitle: string;
    emptyDesc: string;
    emptyShort: string;
    noMatch: string;
    loadError: string;
    actionFailed: string;
    related: string;
    filters: {
      all: string;
      unread: string;
      important: string;
      academic: string;
      schedule: string;
      deadline: string;
      event: string;
      student_services: string;
      system: string;
    };
  };

  // calendar screen
  cal: {
    title: string;
    today: string;
    prev: string;
    next: string;
    week: string;
    month: string;
    searchPlaceholder: string;
    allTypes: string;
    upcoming: string;
    noUpcoming: string;
    noEvents: string;
    addReminder: string;
    reminderAdded: string;
    location: string;
    course: string;
    category: string;
    description: string;
    source: string;
    time: string;
    allDay: string;
    close: string;
    moreEvents: (n: number) => string;
    loadError: string;
  };

  // support tickets screen (list + detail)
  tickets: {
    title: string;
    searchPlaceholder: string;
    statusLabel: string;
    priorityLabel: string;
    categoryLabel: string;
    visibilityLabel: string;
    all: string;
    created: string;
    updated: string;
    viewDetail: string;
    archive: string;
    restore: string;
    delete: string;
    deleteConfirm: string;
    confirmDelete: string;
    cancel: string;
    conversation: string;
    originalQuestion: string;
    attachedSource: string;
    noMatch: string;
    actionFailed: string;
    archivedToast: string;
    restoredToast: string;
    deletedToast: string;
    close: string;
    you: string;
    staff: string;
    systemAuthor: string;
    vis: { active: string; archived: string; deleted: string };
    // PLAN23.6.01 board
    subtitle: string;
    newTicket: string;
    createIntro: string;
    continueReview: string;
    sortLabel: string;
    sort: { updated_desc: string; created_desc: string; priority_desc: string; sla_asc: string };
    dueSoon: string;
    dueOn: (date: string) => string;
    colEmpty: string;
    colOpen: string;
    colInProgress: string;
    colWaiting: string;
    colClosed: string;
  };

  // answer actions
  actViewSource: string;
  actAddCalendar: string;
  actSetReminder: string;
  actForward: string;
  actReport: string;
  forwardedFromChat: string;
  forwardedOk: (id: string) => string;
  forwardFailed: string;

  // PLAN22.6 answer-action set (Vinnie never auto-submits a ticket)
  actPrepareTicket: string;
  actAskFollowUp: string;
  actContactOffice: string;
  actOpenPolicy: string;
  askVinnieAbout: string;

  // Review Ticket drawer (draft → review → send)
  review: {
    banner: string;
    category: string;
    office: string;
    priority: string;
    summary: string;
    summaryPlaceholder: string;
    description: string;
    descriptionPlaceholder: string;
    relatedContext: string;
    noContext: string;
    includeContext: string;
    includeContextHelp: string;
    attachments: string;
    attachmentsLater: string;
    cancel: string;
    saveDraft: string;
    sendToAdmin: string;
    sending: string;
    draftSaved: string;
    submitted: (id: string) => string;
    submitFailed: string;
    close: string;
  };

  // Admin: submitted-ticket management
  adminTickets: {
    title: string;
    subtitle: string;
    colStudent: string;
    colSubject: string;
    colCategory: string;
    colPriority: string;
    colStatus: string;
    colUpdated: string;
    none: string;
    noneDesc: string;
    noMatch: string;
    view: string;
    fromChat: string;
    includedContext: string;
    respond: string;
    respondPlaceholder: string;
    sendReply: string;
    statusUpdated: string;
    replySent: string;
    actionFailed: string;
    // PLAN23.6.01 board + advanced filters
    colWaitingStudent: string;
    colResolved: string;
    assigneeLabel: string;
    unassigned: string;
    assignedTo: string;
    departmentLabel: string;
    dateFrom: string;
    dateTo: string;
  };

  // Admin: notification creation + suggested-question approval
  adminNotif: {
    title: string;
    subtitle: string;
    listHeading: string;
    createHeading: string;
    fTitle: string;
    fTitlePlaceholder: string;
    fMessage: string;
    fMessagePlaceholder: string;
    fCategory: string;
    fPriority: string;
    fAudience: string;
    fEventDate: string;
    fDeadline: string;
    generate: string;
    regenerate: string;
    suggestedHeading: string;
    suggestedHint: string;
    noQuestions: string;
    approve: string;
    approved: string;
    saveDraftBtn: string;
    publish: string;
    publishHint: string;
    publishing: string;
    draftCreated: string;
    publishedToast: string;
    actionFailed: string;
    phase: Record<string, string>;
  };

  // dashboard
  greetingMorning: string;
  todaySchedule: string;
  upcomingDeadlines: string;
  tuitionStatus: string;
  suggestedQuestions: string;
  askAnything: string;
  askCta: string;

  // student dashboard
  dash: {
    studentId: string;
    paidOf: (paid: string, total: string) => string;
    dueNext7: string;
    gpaCredits: string;
    creditsEarned: (earned: number, required: number) => string;
    noClasses: string;
    nextClassDay: (day: string) => string;
    suggested: string[];
  };

  // schedule screen
  sched: {
    weekly: string;
    noClassesTitle: string;
    noClassesDesc: string;
  };

  // tuition screen
  tui: {
    totalCharged: string;
    paidToDate: string;
    outstanding: string;
    nextDue: (amount: string, date: string) => string;
    paymentProgress: string;
    pctPaid: (n: number) => string;
    nextPaymentTitle: string;
    nextPaymentBody: (amount: string, date: string) => string;
    goToPortal: string;
    statement: string;
    colItem: string;
    colTerm: string;
    colAmount: string;
    colStatus: string;
    colDate: string;
    paidOn: (date: string) => string;
    dueOn: (date: string) => string;
  };

  // support screen
  sup: {
    highPriority: string;
    opened: (date: string) => string;
    resolution: string;
    ticketCreated: (id: string, dept: string) => string;
    submitFailed: string;
    yourTickets: string;
    noTicketsTitle: string;
    noTicketsDesc: string;
    newRequest: string;
    subject: string;
    subjectPlaceholder: string;
    department: string;
    details: string;
    detailsPlaceholder: string;
    submitting: string;
    submit: string;
  };

  // admin dashboard + shared admin copy
  admin: {
    indexedDocs: string;
    sourcesCrawledToday: string;
    failedCrawls: string;
    unansweredQuestions: string;
    verifiedRate: string;
    lowConfidence: string;
    inboxTitle: string;
    inboxZero: string;
    inboxZeroDesc: string;
    askedTimes: (n: number) => string;
    quickActions: string;
    qaUpload: string;
    qaManageSources: string;
    qaReview: string;
    qaAnalytics: string;

    // sources
    allSources: string;
    addSource: string;
    loadSourcesError: string;
    noSourcesTitle: string;
    noSourcesDesc: string;
    colSourceName: string;
    colType: string;
    colCategory: string;
    colStatus: string;
    colChunks: string;
    colLastCrawled: string;
    colLastIndexed: string;
    colActions: string;
    official: string;
    recrawl: string;
    chunks: string;
    disable: string;
    recrawled: (name: string, n: number) => string;
    recrawlFailed: string;
    disabled: (name: string) => string;
    disableFailed: string;
    chunksInfo: (name: string, n: number) => string;
    sourcesNote: string;

    // upload
    stepSource: string;
    stepPreview: string;
    stepApprove: string;
    stepIndexed: string;
    sourceTitle: string;
    sourceTitlePlaceholder: string;
    sourceType: string;
    optUrl: string;
    category: string;
    officialUrl: string;
    urlPlaceholder: string;
    urlHint: string;
    uploadFile: (type: string) => string;
    kbSelected: (kb: number) => string;
    clickToChoose: string;
    extractPreview: string;
    extractedPreview: string;
    looksGood: string;
    approveForChatbot: string;
    fTitle: string;
    fSource: string;
    fType: string;
    approveHint: string;
    indexing: string;
    approveIndex: string;
    indexedTitle: string;
    indexedResult: (docs: number, chunks: number, skipped: number) => string;
    addAnother: string;
    viewSources: string;
    indexFailed: string;

    // analytics
    totalQuestions7d: string;
    avgConfidence: string;
    questionsPerDay: string;
    verified: string;
    unanswered: string;
    topTopics: string;

    // logs
    recentEvents: string;
    colTime: string;
    colLevel: string;
    colMessage: string;
    colSource: string;
    logsNote: string;

    // unanswered list
    filters: { all: string; new: string; in_review: string; forwarded: string; resolved: string };
    inbox: string;
    nothingHere: string;
    noMatch: string;
    colQuestion: string;
    colReason: string;
    colDepartment: string;
    colPriority: string;
    colAsked: string;
    colCreated: string;
    resolve: string;

    // unanswered detail
    backToInbox: string;
    notFound: string;
    notFoundDesc: string;
    priorityLabel: (priority: string) => string;
    studentContext: string;
    suggestedDept: string;
    firstAsked: string;
    createAnswer: string;
    answerPlaceholder: string;
    addToKb: string;
    publishing: string;
    publishAnswer: string;
    routeOrAttach: string;
    forwardToDept: string;
    forward: string;
    attachSource: string;
    attach: string;
    markResolved: string;
    actionFailed: string;
    publishedKb: string;
    published: string;
    forwardedTo: (dept: string) => string;
    sourceAttached: string;
    markedResolved: string;
  };

  // day-of-week full names
  dayFull: Record<ScheduleDay, string>;

  // Forum / Discussion Hub
  forum: {
    title: string;
    subtitle: string;
    newTopic: string;
    allCategories: string;
    sortActive: string;
    sortNew: string;
    sortTop: string;
    searchPlaceholder: string;
    topicCount: (n: number) => string;
    commentCount: (n: number) => string;
    viewCount: (n: number) => string;
    by: string;
    reply: string;
    comment: string;
    commentPlaceholder: string;
    replyPlaceholder: string;
    postComment: string;
    postReply: string;
    cancel: string;
    posting: string;
    pinned: string;
    locked: string;
    lockedNotice: string;
    officialAnswer: string;
    markOfficial: string;
    unmarkOfficial: string;
    pin: string;
    unpin: string;
    lock: string;
    unlock: string;
    delete: string;
    moderator: string;
    you: string;
    report: string;
    reportTitle: string;
    reportReasonPlaceholder: string;
    submitReport: string;
    reportedToast: string;
    upvote: string;
    downvote: string;
    viewDiscussion: string;
    backToForum: string;
    titleLabel: string;
    titlePlaceholder: string;
    categoryLabel: string;
    contentLabel: string;
    contentPlaceholder: string;
    tagsLabel: string;
    tagsPlaceholder: string;
    attachmentsLabel: string;
    attachmentUrlPlaceholder: string;
    attachmentLabelPlaceholder: string;
    addLink: string;
    create: string;
    creating: string;
    mentionHint: string;
    mentionNoResults: string;
    emptyTitle: string;
    emptyDesc: string;
    noComments: string;
    createError: string;
    actionFailed: string;
    removed: string;
  };

  // data-driven enum badge labels
  enums: {
    deadlineKind: Record<DeadlineKind, string>;
    tuitionItemStatus: Record<TuitionItemStatus, string>;
    ticketStatus: Record<TicketStatus, string>;
    ticketPriority: Record<TicketPriority, string>;
    ticketCategory: Record<TicketCategory, string>;
    notificationType: Record<NotificationType, string>;
    eventType: Record<CalendarEventType, string>;
    sourceStatus: Record<SourceStatus, string>;
    questionStatus: Record<QuestionStatus, string>;
    questionPriority: Record<QuestionPriority, string>;
    questionReason: Record<QuestionFailureReason, string>;
    logLevel: Record<LogLevel, string>;
    category: Record<SourceCategory, string>;
    department: Record<string, string>;
  };
}

// Canonical department keys (English) — the value sent to the backend stays stable; only
// the displayed label is localized via enums.department.
export const DEPARTMENTS = [
  "Office of the Registrar",
  "Student Financial Services",
  "Office of Financial Aid",
  "Student Affairs",
  "Academic Advising",
  "IT Help Desk",
];

const en: PortalStrings = {
  productName: "Student Copilot",
  productNameFull: "VinUni Student Copilot",
  productTagline: "VinUni · 24/7 AI student support",
  studentPortal: "Student",
  adminPortal: "Admin",
  nav: {
    dashboard: "Dashboard",
    chat: "Ask Vinnie",
    schedule: "Calendar",
    notifications: "Notifications",
    tuition: "Tuition & Fees",
    tickets: "Support Tickets",
    adminDashboard: "Admin Dashboard",
    adminTickets: "Support Tickets",
    adminNotifications: "Notifications",
    sources: "Knowledge Sources",
    upload: "Upload Document",
    questions: "Unanswered Questions",
    analytics: "Analytics",
    logs: "System Logs",
  },
  roleStudent: "Student",
  roleAdmin: "Admin",
  signOut: "Sign out",
  adminConsole: "Admin Console",
  adminConsoleSub: "Manage official sources, unresolved questions, and chatbot quality.",
  adminWarning:
    "Only authorized staff can upload sources, approve answers, and review unresolved student questions.",
  studentChatNote:
    "You are viewing this as a Student. Personalized answers use your own schedule, tuition status, and deadlines.",
  authFooter: "VinUni Student Copilot · 24/7 verified student support",
  login: {
    title: "Sign in to VinUni Student Copilot",
    subtitle: "24/7 verified student support powered by official VinUni sources",
    emailLabel: "University email",
    passwordLabel: "Password",
    signIn: "Sign in",
    continueStudent: "Continue as Student",
    continueAdmin: "Continue as Admin",
    sso: "Continue with VinUni SSO",
    ssoHint: "Demo: signs in as the student account",
    securityNote: "Your access is based on your VinUni role and permissions.",
    demoStudent: "Student demo account",
    demoAdmin: "Admin demo account",
    or: "or",
  },
  access: {
    title: "Access denied",
    message: "You do not have permission to view this area.",
    backToDashboard: "Back to my dashboard",
    signOut: "Sign out",
  },
  viewAll: "View all",
  openSource: "Open source",
  loading: "Loading…",
  empty: "Nothing here yet.",
  retry: "Retry",
  errorGeneric: "Couldn't load this. Try again.",
  back: "Back",
  view: "View",
  year: "Year",
  daysLeft: (n) => (n === 1 ? "1 day left" : `${n} days left`),
  dueToday: "Due today",
  overdue: "Overdue",
  modeGeneral: "General VinUni Info",
  modePersonal: "My Student Info",
  modeHint: "Personalized answers use your program, schedule, deadlines and tuition.",
  personalizedAnswer: "Personalized answer",
  chatSuggested: [
    "What deadlines do I have this week?",
    "When is my next class?",
    "Show my notifications",
    "What events are happening this week?",
    "How do I submit a support request?",
    "What is the course withdrawal process?",
  ],
  somethingWrong: "Something went wrong.",
  chatWelcomeTitle: (name) => `Hi ${name || "there"}, I'm Vinnie.`,
  chatWelcomeSub:
    "I can help with your schedule, tickets, academic policies, events, and student services.",
  chatTrustNote:
    "Answers use official VinUni sources when available. Personalized answers may use your schedule, tickets, and academic profile.",
  chatHistory: {
    title: "Conversations",
    newChat: "New chat",
    untitled: "New conversation",
    empty: "No conversations yet.",
    rename: "Rename",
    delete: "Delete",
    deleteConfirm: "Delete this conversation? This can't be undone.",
    actions: "Conversation actions",
    save: "Save",
    cancel: "Cancel",
    processing: "Processing…",
    stillWaiting: "This conversation is still receiving an answer",
  },

  notif: {
    title: "Notifications",
    markAllRead: "Mark all read",
    markRead: "Mark as read",
    markUnread: "Mark as unread",
    markImportant: "Mark important",
    unmarkImportant: "Remove important",
    archive: "Archive",
    delete: "Delete",
    deleteConfirm: "Delete this notification? This can't be undone.",
    confirmDelete: "Delete",
    cancel: "Cancel",
    unreadCount: (n) => (n === 1 ? "1 unread" : `${n} unread`),
    emptyTitle: "You're all caught up",
    emptyDesc: "New notifications about deadlines, schedule, and events will appear here.",
    emptyShort: "No notifications yet",
    noMatch: "No notifications match this filter.",
    loadError: "Couldn't load notifications.",
    actionFailed: "Action failed. Try again.",
    related: "Related",
    filters: {
      all: "All",
      unread: "Unread",
      important: "Important",
      academic: "Academic",
      schedule: "Schedule",
      deadline: "Deadline",
      event: "Event",
      student_services: "Student Services",
      system: "System",
    },
  },

  cal: {
    title: "Calendar",
    today: "Today",
    prev: "Previous",
    next: "Next",
    week: "Week",
    month: "Month",
    searchPlaceholder: "Search events…",
    allTypes: "All types",
    upcoming: "Upcoming",
    noUpcoming: "Nothing coming up.",
    noEvents: "No events match your filters.",
    addReminder: "Add reminder",
    reminderAdded: "Reminder added ✓",
    location: "Location",
    course: "Course",
    category: "Category",
    description: "Description",
    source: "Source",
    time: "Time",
    allDay: "All day",
    close: "Close",
    moreEvents: (n) => `+${n} more`,
    loadError: "Couldn't load the calendar.",
  },

  tickets: {
    title: "Support tickets",
    searchPlaceholder: "Search tickets…",
    statusLabel: "Status",
    priorityLabel: "Priority",
    categoryLabel: "Category",
    visibilityLabel: "Visibility",
    all: "All",
    created: "Created",
    updated: "Updated",
    viewDetail: "View detail",
    archive: "Hide / archive",
    restore: "Restore",
    delete: "Delete",
    deleteConfirm: "Remove this ticket? It moves to Deleted and is hidden from your active list.",
    confirmDelete: "Remove",
    cancel: "Cancel",
    conversation: "Conversation",
    originalQuestion: "Original question",
    attachedSource: "Attached source",
    noMatch: "No tickets match your filters.",
    actionFailed: "Action failed. Try again.",
    archivedToast: "Ticket archived.",
    restoredToast: "Ticket restored.",
    deletedToast: "Ticket removed.",
    close: "Close",
    you: "You",
    staff: "Staff",
    systemAuthor: "System",
    vis: { active: "Active", archived: "Hidden / Archived", deleted: "Deleted" },
    subtitle: "Track your requests and responses from VinUni support teams.",
    newTicket: "New ticket",
    createIntro: "Fill in the details, then review before it's sent to the support team.",
    continueReview: "Continue to review",
    sortLabel: "Sort",
    sort: {
      updated_desc: "Recently updated",
      created_desc: "Newest",
      priority_desc: "Priority",
      sla_asc: "Due soonest",
    },
    dueSoon: "Due soon",
    dueOn: (date) => `Due ${date}`,
    colEmpty: "Nothing here.",
    colOpen: "Open",
    colInProgress: "In progress",
    colWaiting: "Waiting",
    colClosed: "Closed",
  },
  actViewSource: "View source",
  actAddCalendar: "Add to calendar",
  actSetReminder: "Set reminder",
  actForward: "Forward to admin",
  actReport: "Report issue",
  forwardedFromChat: "Forwarded from chat",
  forwardedOk: (id) => `Forwarded to admin — ticket ${id} created.`,
  forwardFailed: "Couldn't forward right now. Try again.",
  actPrepareTicket: "Prepare support ticket",
  actAskFollowUp: "Ask follow-up",
  actContactOffice: "Contact office",
  actOpenPolicy: "Open source",
  askVinnieAbout: "Ask Vinnie about this",
  review: {
    banner: "Vinnie prepared a support ticket draft. Please review it before sending.",
    category: "Category",
    office: "Assigned office",
    priority: "Priority",
    summary: "Summary",
    summaryPlaceholder: "Short summary of your issue",
    description: "Description",
    descriptionPlaceholder: "Describe your issue for the staff team",
    relatedContext: "Related conversation context",
    noContext: "No chat context attached.",
    includeContext: "Include relevant chat context",
    includeContextHelp:
      "Only the short summary above is shared with staff — never your full chat history, GPA, or tuition.",
    attachments: "Attachments",
    attachmentsLater: "Attachments are coming soon.",
    cancel: "Cancel",
    saveDraft: "Save draft",
    sendToAdmin: "Send to Admin",
    sending: "Sending…",
    draftSaved: "Draft saved. It stays private until you send it.",
    submitted: (id) => `Ticket ${id} submitted to admin.`,
    submitFailed: "Couldn't submit the ticket. Try again.",
    close: "Close",
  },
  adminTickets: {
    title: "Support tickets",
    subtitle: "Tickets students have submitted for staff support.",
    colStudent: "Student",
    colSubject: "Subject",
    colCategory: "Category",
    colPriority: "Priority",
    colStatus: "Status",
    colUpdated: "Updated",
    none: "No submitted tickets yet",
    noneDesc: "Drafts students haven't sent are never shown here.",
    noMatch: "No tickets match your filters.",
    view: "Open",
    fromChat: "Prepared from a chat conversation",
    includedContext: "Chat context included by the student",
    respond: "Respond to student",
    respondPlaceholder: "Write a reply to the student…",
    sendReply: "Send reply",
    statusUpdated: "Status updated.",
    replySent: "Reply sent to the student.",
    actionFailed: "Action failed. Try again.",
    colWaitingStudent: "Waiting for student",
    colResolved: "Resolved",
    assigneeLabel: "Assignee",
    unassigned: "Unassigned",
    assignedTo: "Assigned to",
    departmentLabel: "Department",
    dateFrom: "From",
    dateTo: "To",
  },
  adminNotif: {
    title: "Notifications",
    subtitle: "Create announcements and approve the questions Vinnie suggests from them.",
    listHeading: "Existing notifications",
    createHeading: "Create notification",
    fTitle: "Title",
    fTitlePlaceholder: "e.g. Course drop deadline approaching",
    fMessage: "Content",
    fMessagePlaceholder: "What students need to know…",
    fCategory: "Category",
    fPriority: "Priority",
    fAudience: "Target audience",
    fEventDate: "Event date",
    fDeadline: "Deadline",
    generate: "Generate suggested questions",
    regenerate: "Regenerate questions",
    suggestedHeading: "Suggested questions",
    suggestedHint: "Edit the wording and approve the ones students should see.",
    noQuestions: "Generate questions from the category and dates above.",
    approve: "Approve",
    approved: "Approved",
    saveDraftBtn: "Save as draft",
    publish: "Publish notification",
    publishHint: "Approve at least one question to publish.",
    publishing: "Publishing…",
    draftCreated: "Notification saved as draft.",
    publishedToast: "Notification published — students will see it.",
    actionFailed: "Action failed. Try again.",
    phase: {
      early: "Discovery",
      near_deadline: "Action",
      overdue: "Recovery",
      active: "General",
    },
  },
  greetingMorning: "Welcome back",
  todaySchedule: "Today's schedule",
  upcomingDeadlines: "Upcoming deadlines",
  tuitionStatus: "Tuition status",
  suggestedQuestions: "Suggested questions",
  askAnything: "Ask about deadlines, tuition, policies, services…",
  askCta: "Ask AI",

  dash: {
    studentId: "Student ID",
    paidOf: (paid, total) => `${paid} paid of ${total}`,
    dueNext7: "due in the next 7 days",
    gpaCredits: "GPA · Credits",
    creditsEarned: (earned, required) => `${earned} / ${required} credits earned`,
    noClasses: "No classes scheduled.",
    nextClassDay: (day) => `No classes today — showing next class day (${day}).`,
    suggested: [
      "What deadlines do I have this week?",
      "When is my next class?",
      "What events are happening this week?",
    ],
  },

  sched: {
    weekly: "Weekly class schedule",
    noClassesTitle: "No classes on file",
    noClassesDesc: "Your registered classes will appear here.",
  },

  tui: {
    totalCharged: "Total charged",
    paidToDate: "Paid to date",
    outstanding: "Outstanding balance",
    nextDue: (amount, date) => `Next ${amount} due ${date}`,
    paymentProgress: "Payment progress",
    pctPaid: (n) => `${n}% paid`,
    nextPaymentTitle: "💳 Next payment due",
    nextPaymentBody: (amount, date) =>
      `${amount} is due on ${date}. Pay via the VinUni Student Financial Services portal to avoid a late fee.`,
    goToPortal: "Go to payment portal",
    statement: "Statement of account",
    colItem: "Item",
    colTerm: "Term",
    colAmount: "Amount",
    colStatus: "Status",
    colDate: "Date",
    paidOn: (date) => `Paid ${date}`,
    dueOn: (date) => `Due ${date}`,
  },

  sup: {
    highPriority: "high priority",
    opened: (date) => `opened ${date}`,
    resolution: "Resolution",
    ticketCreated: (id, dept) => `Ticket ${id} created — ${dept} will follow up.`,
    submitFailed: "Couldn't submit the ticket. Try again.",
    yourTickets: "Your tickets & forwarded questions",
    noTicketsTitle: "No tickets yet",
    noTicketsDesc: "Questions you forward to admin from the chat will show up here.",
    newRequest: "New support request",
    subject: "Subject",
    subjectPlaceholder: "e.g. Scholarship renewal criteria",
    department: "Department",
    details: "Details",
    detailsPlaceholder: "Describe what you need help with…",
    submitting: "Submitting…",
    submit: "Submit ticket",
  },

  admin: {
    indexedDocs: "Indexed documents",
    sourcesCrawledToday: "Sources crawled today",
    failedCrawls: "Failed crawls",
    unansweredQuestions: "Unanswered questions",
    verifiedRate: "Verified answer rate",
    lowConfidence: "Low-confidence responses",
    inboxTitle: "Unanswered questions inbox",
    inboxZero: "Inbox zero 🎉",
    inboxZeroDesc: "No unanswered questions.",
    askedTimes: (n) => `${n}× asked`,
    quickActions: "Quick actions",
    qaUpload: "Upload a document",
    qaManageSources: "Manage knowledge sources",
    qaReview: "Review unanswered questions",
    qaAnalytics: "View analytics",

    allSources: "All sources",
    addSource: "Add source",
    loadSourcesError: "Couldn't load sources from the backend.",
    noSourcesTitle: "No sources indexed",
    noSourcesDesc: "Upload a document or crawl a URL to populate the knowledge base.",
    colSourceName: "Source name",
    colType: "Type",
    colCategory: "Category",
    colStatus: "Status",
    colChunks: "Chunks",
    colLastCrawled: "Last crawled",
    colLastIndexed: "Last indexed",
    colActions: "Actions",
    official: "Official",
    recrawl: "Re-crawl",
    chunks: "Chunks",
    disable: "Disable",
    recrawled: (name, n) => `Re-crawled “${name}” — ${n} chunks indexed.`,
    recrawlFailed: "Re-crawl failed. Check the backend is running.",
    disabled: (name) => `Disabled “${name}”.`,
    disableFailed: "Couldn't disable the source.",
    chunksInfo: (name, n) => `“${name}” has ${n} indexed chunks.`,
    sourcesNote:
      "Live data from GET /sources; re-crawl posts to /ingest/run. Falls back to demo rows when the backend is offline.",

    stepSource: "Source",
    stepPreview: "Preview",
    stepApprove: "Approve",
    stepIndexed: "Indexed",
    sourceTitle: "Source title",
    sourceTitlePlaceholder: "e.g. Academic Calendar 2025–2026",
    sourceType: "Source type",
    optUrl: "Official URL",
    category: "Category",
    officialUrl: "Official URL",
    urlPlaceholder: "https://vinuni.edu.vn/…",
    urlHint: "URLs crawl + index through the live /ingest/run pipeline.",
    uploadFile: (type) => `Upload ${type} file`,
    kbSelected: (kb) => `${kb} KB selected`,
    clickToChoose: "Click to choose a file",
    extractPreview: "Extract & preview",
    extractedPreview: "Extracted text preview",
    looksGood: "Looks good — continue",
    approveForChatbot: "Approve for chatbot",
    fTitle: "Title",
    fSource: "Source",
    fType: "Type",
    approveHint:
      "Approving indexes this source into the vector store so the chatbot can cite it.",
    indexing: "Indexing…",
    approveIndex: "Approve & index",
    indexedTitle: "Indexed into the knowledge base",
    indexedResult: (docs, chunks, skipped) =>
      `${docs} document(s) processed · ${chunks} chunks indexed · ${skipped} skipped.`,
    addAnother: "Add another",
    viewSources: "View sources",
    indexFailed: "Indexing failed. Check the backend.",

    totalQuestions7d: "Total questions (7 days)",
    avgConfidence: "Average confidence",
    questionsPerDay: "Questions per day",
    verified: "Verified",
    unanswered: "Unanswered",
    topTopics: "Top topics",

    recentEvents: "Recent system events",
    colTime: "Time",
    colLevel: "Level",
    colMessage: "Message",
    colSource: "Source",
    logsNote:
      "Demo feed. The backend already emits structured logs (request IDs via core/observability); wire GET /admin/logs to stream them here.",

    filters: { all: "All", new: "New", in_review: "In review", forwarded: "Forwarded", resolved: "Resolved" },
    inbox: "Inbox",
    nothingHere: "Nothing here",
    noMatch: "No questions match this filter.",
    colQuestion: "Question",
    colReason: "Reason",
    colDepartment: "Department",
    colPriority: "Priority",
    colAsked: "Asked",
    colCreated: "Created",
    resolve: "Resolve",

    backToInbox: "← Back to inbox",
    notFound: "Question not found",
    notFoundDesc: "It may have been resolved or removed.",
    priorityLabel: (priority) => `${priority} priority`,
    studentContext: "Student context (anonymized)",
    suggestedDept: "Suggested department",
    firstAsked: "First asked",
    createAnswer: "Create official answer",
    answerPlaceholder: "Write a verified answer citing official policy…",
    addToKb: "Add this answer to the knowledge base",
    publishing: "Publishing…",
    publishAnswer: "Publish official answer",
    routeOrAttach: "Route or attach",
    forwardToDept: "Forward to department",
    forward: "Forward",
    attachSource: "Attach official source",
    attach: "Attach",
    markResolved: "✓ Mark as resolved",
    actionFailed: "Action failed. Try again.",
    publishedKb: "Official answer published and added to knowledge base.",
    published: "Official answer published.",
    forwardedTo: (dept) => `Forwarded to ${dept}.`,
    sourceAttached: "Source attached to this question.",
    markedResolved: "Marked as resolved.",
  },

  dayFull: {
    Mon: "Monday",
    Tue: "Tuesday",
    Wed: "Wednesday",
    Thu: "Thursday",
    Fri: "Friday",
    Sat: "Saturday",
    Sun: "Sunday",
  },

  forum: {
    title: "Discussion Hub",
    subtitle: "Ask, share and discuss with the VinUni student community.",
    newTopic: "New topic",
    allCategories: "All topics",
    sortActive: "Active",
    sortNew: "New",
    sortTop: "Top",
    searchPlaceholder: "Search discussions…",
    topicCount: (n) => `${n} ${n === 1 ? "topic" : "topics"}`,
    commentCount: (n) => `${n} ${n === 1 ? "comment" : "comments"}`,
    viewCount: (n) => `${n} ${n === 1 ? "view" : "views"}`,
    by: "by",
    reply: "Reply",
    comment: "Comment",
    commentPlaceholder: "Add a comment… use @ to mention someone",
    replyPlaceholder: "Write a reply… use @ to mention someone",
    postComment: "Post comment",
    postReply: "Post reply",
    cancel: "Cancel",
    posting: "Posting…",
    pinned: "Pinned",
    locked: "Locked",
    lockedNotice: "This topic is locked. New comments are disabled.",
    officialAnswer: "Official answer",
    markOfficial: "Mark as official",
    unmarkOfficial: "Unmark official",
    pin: "Pin",
    unpin: "Unpin",
    lock: "Lock",
    unlock: "Unlock",
    delete: "Delete",
    moderator: "Moderator",
    you: "You",
    report: "Report",
    reportTitle: "Report content",
    reportReasonPlaceholder: "Tell moderators what's wrong…",
    submitReport: "Submit report",
    reportedToast: "Thanks — moderators will review this.",
    upvote: "Upvote",
    downvote: "Downvote",
    viewDiscussion: "View discussion",
    backToForum: "Back to forum",
    titleLabel: "Title",
    titlePlaceholder: "What do you want to discuss?",
    categoryLabel: "Category",
    contentLabel: "Details",
    contentPlaceholder: "Share the details… use @ to mention someone",
    tagsLabel: "Tags",
    tagsPlaceholder: "Add a tag and press Enter",
    attachmentsLabel: "Links",
    attachmentUrlPlaceholder: "https://…",
    attachmentLabelPlaceholder: "Label (optional)",
    addLink: "Add link",
    create: "Post topic",
    creating: "Posting…",
    mentionHint: "Type @ to mention a member",
    mentionNoResults: "No members found",
    emptyTitle: "No discussions yet",
    emptyDesc: "Be the first to start a conversation.",
    noComments: "No comments yet — start the discussion.",
    createError: "Couldn't post. Please try again.",
    actionFailed: "Something went wrong. Please try again.",
    removed: "[removed]",
  },

  enums: {
    deadlineKind: {
      assignment: "assignment",
      exam: "exam",
      registration: "registration",
      tuition: "tuition",
      administrative: "administrative",
    },
    tuitionItemStatus: { paid: "paid", due: "due", overdue: "overdue", upcoming: "upcoming" },
    ticketStatus: {
      draft: "draft",
      submitted: "submitted",
      open: "open",
      in_review: "in review",
      in_progress: "in progress",
      waiting_for_student: "waiting for you",
      waiting_on_student: "waiting for student",
      resolved: "resolved",
      closed: "closed",
    },
    ticketPriority: { low: "low", medium: "medium", high: "high", urgent: "urgent" },
    ticketCategory: {
      academic: "Academic",
      schedule: "Schedule",
      student_services: "Student Services",
      technical: "Technical",
      other: "Other",
    },
    notificationType: {
      academic: "Academic",
      schedule: "Schedule",
      deadline: "Deadline",
      event: "Event",
      student_services: "Student Services",
      system: "System",
      forum: "Forum",
    },
    eventType: {
      class: "Class",
      deadline: "Deadline",
      exam: "Exam",
      event: "Event",
      reminder: "Reminder",
    },
    sourceStatus: {
      indexed: "indexed",
      crawling: "crawling",
      failed: "failed",
      disabled: "disabled",
      pending: "pending",
    },
    questionStatus: { new: "new", in_review: "in review", forwarded: "forwarded", resolved: "resolved" },
    questionPriority: { low: "low", medium: "medium", high: "high" },
    questionReason: {
      no_verified_source: "No verified source",
      low_confidence: "Low confidence",
      out_of_scope: "Out of scope",
      ambiguous: "Ambiguous",
    },
    logLevel: { info: "info", warn: "warn", error: "error", success: "success" },
    category: {
      Academic: "Academic",
      Tuition: "Tuition",
      Events: "Events",
      "Student Services": "Student Services",
      Schedule: "Schedule",
    },
    department: {
      "Office of the Registrar": "Office of the Registrar",
      "Student Financial Services": "Student Financial Services",
      "Office of Financial Aid": "Office of Financial Aid",
      "Student Affairs": "Student Affairs",
      "Academic Advising": "Academic Advising",
      "IT Help Desk": "IT Help Desk",
    },
  },
};

const vi: PortalStrings = {
  productName: "Student Copilot",
  productNameFull: "VinUni Student Copilot",
  productTagline: "VinUni · Hỗ trợ sinh viên AI 24/7",
  studentPortal: "Sinh viên",
  adminPortal: "Quản trị",
  nav: {
    dashboard: "Tổng quan",
    chat: "Hỏi AI",
    schedule: "Lịch học",
    notifications: "Thông báo",
    tuition: "Học phí",
    tickets: "Yêu cầu hỗ trợ",
    adminDashboard: "Bảng quản trị",
    adminTickets: "Yêu cầu hỗ trợ",
    adminNotifications: "Thông báo",
    sources: "Nguồn tri thức",
    upload: "Tải tài liệu",
    questions: "Câu hỏi chưa trả lời",
    analytics: "Phân tích",
    logs: "Nhật ký hệ thống",
  },
  roleStudent: "Sinh viên",
  roleAdmin: "Quản trị",
  signOut: "Đăng xuất",
  adminConsole: "Trang quản trị",
  adminConsoleSub: "Quản lý nguồn chính thức, câu hỏi chưa giải quyết và chất lượng chatbot.",
  adminWarning:
    "Chỉ nhân viên được ủy quyền mới có thể tải nguồn, duyệt câu trả lời và xem xét câu hỏi chưa giải quyết của sinh viên.",
  studentChatNote:
    "Bạn đang xem với vai trò Sinh viên. Câu trả lời cá nhân hóa dùng lịch học, tình trạng học phí và hạn chót của bạn.",
  authFooter: "VinUni Student Copilot · Hỗ trợ sinh viên đã xác minh 24/7",
  login: {
    title: "Đăng nhập VinUni Student Copilot",
    subtitle: "Hỗ trợ sinh viên 24/7 với câu trả lời đã xác minh từ nguồn chính thức VinUni",
    emailLabel: "Email trường",
    passwordLabel: "Mật khẩu",
    signIn: "Đăng nhập",
    continueStudent: "Tiếp tục với vai trò Sinh viên",
    continueAdmin: "Tiếp tục với vai trò Quản trị",
    sso: "Tiếp tục với VinUni SSO",
    ssoHint: "Demo: đăng nhập bằng tài khoản sinh viên",
    securityNote: "Quyền truy cập dựa trên vai trò và quyền hạn VinUni của bạn.",
    demoStudent: "Tài khoản demo Sinh viên",
    demoAdmin: "Tài khoản demo Quản trị",
    or: "hoặc",
  },
  access: {
    title: "Truy cập bị từ chối",
    message: "Bạn không có quyền xem khu vực này.",
    backToDashboard: "Về trang của tôi",
    signOut: "Đăng xuất",
  },
  viewAll: "Xem tất cả",
  openSource: "Mở nguồn",
  loading: "Đang tải…",
  empty: "Chưa có gì ở đây.",
  retry: "Thử lại",
  errorGeneric: "Không tải được. Thử lại nhé.",
  back: "Quay lại",
  view: "Xem",
  year: "Năm",
  daysLeft: (n) => (n === 1 ? "còn 1 ngày" : `còn ${n} ngày`),
  dueToday: "Hạn hôm nay",
  overdue: "Quá hạn",
  modeGeneral: "Thông tin chung VinUni",
  modePersonal: "Thông tin của tôi",
  modeHint: "Câu trả lời cá nhân hóa dùng chương trình, lịch học, hạn chót và học phí của bạn.",
  personalizedAnswer: "Câu trả lời cá nhân hóa",
  chatSuggested: [
    "Tuần này tôi có những hạn chót nào?",
    "Lớp học tiếp theo của tôi khi nào?",
    "Xem thông báo của tôi",
    "Tuần này có sự kiện gì?",
    "Làm sao để gửi yêu cầu hỗ trợ?",
    "Quy trình rút môn học như thế nào?",
  ],
  somethingWrong: "Đã có lỗi xảy ra.",
  chatWelcomeTitle: (name) => `Chào ${name || "bạn"}, mình là Vinnie.`,
  chatWelcomeSub:
    "Mình có thể giúp về lịch học, phiếu hỗ trợ, chính sách học vụ, sự kiện và dịch vụ sinh viên.",
  chatTrustNote:
    "Câu trả lời ưu tiên dùng nguồn chính thức của VinUni khi có. Câu trả lời cá nhân hóa có thể dùng lịch học, phiếu hỗ trợ và hồ sơ học vụ của bạn.",
  chatHistory: {
    title: "Cuộc trò chuyện",
    newChat: "Cuộc trò chuyện mới",
    untitled: "Cuộc trò chuyện mới",
    empty: "Chưa có cuộc trò chuyện nào.",
    rename: "Đổi tên",
    delete: "Xoá",
    deleteConfirm: "Xoá cuộc trò chuyện này? Không thể hoàn tác.",
    actions: "Tùy chọn cuộc trò chuyện",
    save: "Lưu",
    cancel: "Huỷ",
    processing: "Đang xử lý…",
    stillWaiting: "Cuộc trò chuyện này vẫn đang chờ câu trả lời",
  },

  notif: {
    title: "Thông báo",
    markAllRead: "Đánh dấu đã đọc tất cả",
    markRead: "Đánh dấu đã đọc",
    markUnread: "Đánh dấu chưa đọc",
    markImportant: "Đánh dấu quan trọng",
    unmarkImportant: "Bỏ quan trọng",
    archive: "Lưu trữ",
    delete: "Xóa",
    deleteConfirm: "Xóa thông báo này? Không thể hoàn tác.",
    confirmDelete: "Xóa",
    cancel: "Hủy",
    unreadCount: (n) => `${n} chưa đọc`,
    emptyTitle: "Bạn đã xem hết",
    emptyDesc: "Thông báo mới về hạn chót, lịch học và sự kiện sẽ hiển thị ở đây.",
    emptyShort: "Chưa có thông báo nào",
    noMatch: "Không có thông báo nào khớp bộ lọc này.",
    loadError: "Không tải được thông báo.",
    actionFailed: "Thao tác thất bại. Thử lại nhé.",
    related: "Liên quan",
    filters: {
      all: "Tất cả",
      unread: "Chưa đọc",
      important: "Quan trọng",
      academic: "Học vụ",
      schedule: "Lịch học",
      deadline: "Hạn chót",
      event: "Sự kiện",
      student_services: "Dịch vụ sinh viên",
      system: "Hệ thống",
    },
  },

  cal: {
    title: "Lịch",
    today: "Hôm nay",
    prev: "Trước",
    next: "Sau",
    week: "Tuần",
    month: "Tháng",
    searchPlaceholder: "Tìm sự kiện…",
    allTypes: "Tất cả loại",
    upcoming: "Sắp tới",
    noUpcoming: "Chưa có gì sắp tới.",
    noEvents: "Không có sự kiện nào khớp bộ lọc.",
    addReminder: "Thêm nhắc nhở",
    reminderAdded: "Đã thêm nhắc nhở ✓",
    location: "Địa điểm",
    course: "Môn học",
    category: "Danh mục",
    description: "Mô tả",
    source: "Nguồn",
    time: "Thời gian",
    allDay: "Cả ngày",
    close: "Đóng",
    moreEvents: (n) => `+${n} nữa`,
    loadError: "Không tải được lịch.",
  },

  tickets: {
    title: "Yêu cầu hỗ trợ",
    searchPlaceholder: "Tìm phiếu…",
    statusLabel: "Trạng thái",
    priorityLabel: "Ưu tiên",
    categoryLabel: "Danh mục",
    visibilityLabel: "Hiển thị",
    all: "Tất cả",
    created: "Tạo lúc",
    updated: "Cập nhật",
    viewDetail: "Xem chi tiết",
    archive: "Ẩn / lưu trữ",
    restore: "Khôi phục",
    delete: "Xóa",
    deleteConfirm: "Gỡ phiếu này? Phiếu sẽ chuyển sang mục Đã xóa và ẩn khỏi danh sách đang hoạt động.",
    confirmDelete: "Gỡ",
    cancel: "Hủy",
    conversation: "Hội thoại",
    originalQuestion: "Câu hỏi gốc",
    attachedSource: "Nguồn đính kèm",
    noMatch: "Không có phiếu nào khớp bộ lọc.",
    actionFailed: "Thao tác thất bại. Thử lại nhé.",
    archivedToast: "Đã lưu trữ phiếu.",
    restoredToast: "Đã khôi phục phiếu.",
    deletedToast: "Đã gỡ phiếu.",
    close: "Đóng",
    you: "Bạn",
    staff: "Cán bộ",
    systemAuthor: "Hệ thống",
    vis: { active: "Đang hoạt động", archived: "Ẩn / Lưu trữ", deleted: "Đã xóa" },
    subtitle: "Theo dõi yêu cầu và phản hồi từ các phòng ban hỗ trợ VinUni.",
    newTicket: "Tạo phiếu",
    createIntro: "Điền thông tin, sau đó xem lại trước khi gửi cho đội ngũ hỗ trợ.",
    continueReview: "Tiếp tục xem lại",
    sortLabel: "Sắp xếp",
    sort: {
      updated_desc: "Cập nhật gần đây",
      created_desc: "Mới nhất",
      priority_desc: "Ưu tiên",
      sla_asc: "Sắp đến hạn nhất",
    },
    dueSoon: "Sắp đến hạn",
    dueOn: (date) => `Hạn ${date}`,
    colEmpty: "Chưa có phiếu nào.",
    colOpen: "Mở",
    colInProgress: "Đang xử lý",
    colWaiting: "Chờ phản hồi",
    colClosed: "Đã đóng",
  },
  actViewSource: "Xem nguồn",
  actAddCalendar: "Thêm vào lịch",
  actSetReminder: "Đặt nhắc nhở",
  actForward: "Chuyển cho quản trị",
  actReport: "Báo lỗi",
  forwardedFromChat: "Chuyển từ hội thoại",
  forwardedOk: (id) => `Đã chuyển cho quản trị — đã tạo phiếu ${id}.`,
  forwardFailed: "Chưa chuyển được lúc này. Thử lại nhé.",
  actPrepareTicket: "Soạn phiếu hỗ trợ",
  actAskFollowUp: "Hỏi tiếp",
  actContactOffice: "Liên hệ phòng ban",
  actOpenPolicy: "Mở nguồn",
  askVinnieAbout: "Hỏi Vinnie về việc này",
  review: {
    banner: "Vinnie đã soạn sẵn một phiếu hỗ trợ. Vui lòng xem lại trước khi gửi.",
    category: "Danh mục",
    office: "Phòng ban phụ trách",
    priority: "Ưu tiên",
    summary: "Tiêu đề",
    summaryPlaceholder: "Tóm tắt ngắn gọn vấn đề của bạn",
    description: "Mô tả",
    descriptionPlaceholder: "Mô tả vấn đề để cán bộ hỗ trợ",
    relatedContext: "Ngữ cảnh hội thoại liên quan",
    noContext: "Không đính kèm ngữ cảnh hội thoại.",
    includeContext: "Đính kèm ngữ cảnh hội thoại liên quan",
    includeContextHelp:
      "Chỉ phần tóm tắt ngắn ở trên được chia sẻ với cán bộ — không bao giờ gửi toàn bộ hội thoại, GPA hay học phí.",
    attachments: "Tệp đính kèm",
    attachmentsLater: "Tính năng đính kèm sẽ sớm có.",
    cancel: "Hủy",
    saveDraft: "Lưu nháp",
    sendToAdmin: "Gửi cho quản trị",
    sending: "Đang gửi…",
    draftSaved: "Đã lưu nháp. Phiếu vẫn riêng tư cho đến khi bạn gửi.",
    submitted: (id) => `Đã gửi phiếu ${id} cho quản trị.`,
    submitFailed: "Chưa gửi được phiếu. Thử lại nhé.",
    close: "Đóng",
  },
  adminTickets: {
    title: "Yêu cầu hỗ trợ",
    subtitle: "Các phiếu sinh viên đã gửi để được cán bộ hỗ trợ.",
    colStudent: "Sinh viên",
    colSubject: "Tiêu đề",
    colCategory: "Danh mục",
    colPriority: "Ưu tiên",
    colStatus: "Trạng thái",
    colUpdated: "Cập nhật",
    none: "Chưa có phiếu nào được gửi",
    noneDesc: "Bản nháp sinh viên chưa gửi sẽ không bao giờ hiển thị ở đây.",
    noMatch: "Không có phiếu nào khớp bộ lọc.",
    view: "Mở",
    fromChat: "Soạn từ một cuộc hội thoại",
    includedContext: "Sinh viên đã đính kèm ngữ cảnh hội thoại",
    respond: "Phản hồi sinh viên",
    respondPlaceholder: "Viết phản hồi cho sinh viên…",
    sendReply: "Gửi phản hồi",
    statusUpdated: "Đã cập nhật trạng thái.",
    replySent: "Đã gửi phản hồi cho sinh viên.",
    actionFailed: "Thao tác thất bại. Thử lại nhé.",
    colWaitingStudent: "Chờ sinh viên",
    colResolved: "Đã xử lý",
    assigneeLabel: "Người phụ trách",
    unassigned: "Chưa phân công",
    assignedTo: "Phụ trách",
    departmentLabel: "Phòng ban",
    dateFrom: "Từ",
    dateTo: "Đến",
  },
  adminNotif: {
    title: "Thông báo",
    subtitle: "Tạo thông báo và duyệt các câu hỏi Vinnie gợi ý từ thông báo đó.",
    listHeading: "Thông báo hiện có",
    createHeading: "Tạo thông báo",
    fTitle: "Tiêu đề",
    fTitlePlaceholder: "vd. Sắp đến hạn rút môn học",
    fMessage: "Nội dung",
    fMessagePlaceholder: "Điều sinh viên cần biết…",
    fCategory: "Danh mục",
    fPriority: "Ưu tiên",
    fAudience: "Đối tượng",
    fEventDate: "Ngày sự kiện",
    fDeadline: "Hạn chót",
    generate: "Tạo câu hỏi gợi ý",
    regenerate: "Tạo lại câu hỏi",
    suggestedHeading: "Câu hỏi gợi ý",
    suggestedHint: "Chỉnh sửa nội dung và duyệt những câu sinh viên nên thấy.",
    noQuestions: "Tạo câu hỏi từ danh mục và ngày tháng ở trên.",
    approve: "Duyệt",
    approved: "Đã duyệt",
    saveDraftBtn: "Lưu nháp",
    publish: "Đăng thông báo",
    publishHint: "Duyệt ít nhất một câu hỏi để đăng.",
    publishing: "Đang đăng…",
    draftCreated: "Đã lưu thông báo dưới dạng nháp.",
    publishedToast: "Đã đăng thông báo — sinh viên sẽ thấy.",
    actionFailed: "Thao tác thất bại. Thử lại nhé.",
    phase: {
      early: "Khám phá",
      near_deadline: "Hành động",
      overdue: "Khắc phục",
      active: "Chung",
    },
  },
  greetingMorning: "Chào mừng trở lại",
  todaySchedule: "Lịch học hôm nay",
  upcomingDeadlines: "Hạn chót sắp tới",
  tuitionStatus: "Tình trạng học phí",
  suggestedQuestions: "Câu hỏi gợi ý",
  askAnything: "Hỏi về hạn chót, học phí, chính sách, dịch vụ…",
  askCta: "Hỏi AI",

  dash: {
    studentId: "MSSV",
    paidOf: (paid, total) => `Đã đóng ${paid} / ${total}`,
    dueNext7: "đến hạn trong 7 ngày tới",
    gpaCredits: "GPA · Tín chỉ",
    creditsEarned: (earned, required) => `${earned} / ${required} tín chỉ đã đạt`,
    noClasses: "Không có lớp nào.",
    nextClassDay: (day) => `Hôm nay không có lớp — hiển thị ngày học kế tiếp (${day}).`,
    suggested: [
      "Tuần này tôi có những hạn chót nào?",
      "Lớp học tiếp theo của tôi khi nào?",
      "Tuần này có sự kiện gì?",
    ],
  },

  sched: {
    weekly: "Lịch học theo tuần",
    noClassesTitle: "Chưa có lớp học",
    noClassesDesc: "Các lớp bạn đã đăng ký sẽ hiển thị ở đây.",
  },

  tui: {
    totalCharged: "Tổng phải đóng",
    paidToDate: "Đã đóng đến nay",
    outstanding: "Số dư còn lại",
    nextDue: (amount, date) => `Kế tiếp ${amount} đến hạn ${date}`,
    paymentProgress: "Tiến độ thanh toán",
    pctPaid: (n) => `đã đóng ${n}%`,
    nextPaymentTitle: "💳 Khoản thanh toán kế tiếp",
    nextPaymentBody: (amount, date) =>
      `${amount} đến hạn vào ${date}. Hãy thanh toán qua cổng Dịch vụ Tài chính Sinh viên VinUni để tránh phí trễ hạn.`,
    goToPortal: "Đến cổng thanh toán",
    statement: "Sao kê tài khoản",
    colItem: "Khoản mục",
    colTerm: "Học kỳ",
    colAmount: "Số tiền",
    colStatus: "Trạng thái",
    colDate: "Ngày",
    paidOn: (date) => `Đã đóng ${date}`,
    dueOn: (date) => `Hạn ${date}`,
  },

  sup: {
    highPriority: "ưu tiên cao",
    opened: (date) => `mở lúc ${date}`,
    resolution: "Kết quả xử lý",
    ticketCreated: (id, dept) => `Đã tạo phiếu ${id} — ${dept} sẽ phản hồi.`,
    submitFailed: "Chưa gửi được phiếu. Thử lại nhé.",
    yourTickets: "Phiếu & câu hỏi đã chuyển của bạn",
    noTicketsTitle: "Chưa có phiếu nào",
    noTicketsDesc: "Các câu hỏi bạn chuyển cho quản trị từ hội thoại sẽ hiển thị ở đây.",
    newRequest: "Yêu cầu hỗ trợ mới",
    subject: "Tiêu đề",
    subjectPlaceholder: "vd: Tiêu chí gia hạn học bổng",
    department: "Phòng ban",
    details: "Chi tiết",
    detailsPlaceholder: "Mô tả việc bạn cần hỗ trợ…",
    submitting: "Đang gửi…",
    submit: "Gửi phiếu",
  },

  admin: {
    indexedDocs: "Tài liệu đã lập chỉ mục",
    sourcesCrawledToday: "Nguồn thu thập hôm nay",
    failedCrawls: "Lần thu thập lỗi",
    unansweredQuestions: "Câu hỏi chưa trả lời",
    verifiedRate: "Tỉ lệ trả lời đã xác minh",
    lowConfidence: "Câu trả lời độ tin cậy thấp",
    inboxTitle: "Hộp thư câu hỏi chưa trả lời",
    inboxZero: "Hộp thư trống 🎉",
    inboxZeroDesc: "Không có câu hỏi chưa trả lời.",
    askedTimes: (n) => `hỏi ${n} lần`,
    quickActions: "Thao tác nhanh",
    qaUpload: "Tải lên tài liệu",
    qaManageSources: "Quản lý nguồn tri thức",
    qaReview: "Xem xét câu hỏi chưa trả lời",
    qaAnalytics: "Xem phân tích",

    allSources: "Tất cả nguồn",
    addSource: "Thêm nguồn",
    loadSourcesError: "Không tải được nguồn từ backend.",
    noSourcesTitle: "Chưa có nguồn nào",
    noSourcesDesc: "Tải lên tài liệu hoặc thu thập một URL để xây dựng kho tri thức.",
    colSourceName: "Tên nguồn",
    colType: "Loại",
    colCategory: "Danh mục",
    colStatus: "Trạng thái",
    colChunks: "Đoạn",
    colLastCrawled: "Thu thập gần nhất",
    colLastIndexed: "Lập chỉ mục gần nhất",
    colActions: "Thao tác",
    official: "Chính thức",
    recrawl: "Thu thập lại",
    chunks: "Đoạn",
    disable: "Tắt",
    recrawled: (name, n) => `Đã thu thập lại “${name}” — lập chỉ mục ${n} đoạn.`,
    recrawlFailed: "Thu thập lại thất bại. Kiểm tra backend có đang chạy.",
    disabled: (name) => `Đã tắt “${name}”.`,
    disableFailed: "Không tắt được nguồn này.",
    chunksInfo: (name, n) => `“${name}” có ${n} đoạn đã lập chỉ mục.`,
    sourcesNote:
      "Dữ liệu trực tiếp từ GET /sources; thu thập lại gọi /ingest/run. Hiển thị dữ liệu demo khi backend ngoại tuyến.",

    stepSource: "Nguồn",
    stepPreview: "Xem trước",
    stepApprove: "Duyệt",
    stepIndexed: "Đã lập chỉ mục",
    sourceTitle: "Tiêu đề nguồn",
    sourceTitlePlaceholder: "vd: Lịch học vụ 2025–2026",
    sourceType: "Loại nguồn",
    optUrl: "URL chính thức",
    category: "Danh mục",
    officialUrl: "URL chính thức",
    urlPlaceholder: "https://vinuni.edu.vn/…",
    urlHint: "URL sẽ được thu thập + lập chỉ mục qua pipeline /ingest/run trực tiếp.",
    uploadFile: (type) => `Tải lên tệp ${type}`,
    kbSelected: (kb) => `đã chọn ${kb} KB`,
    clickToChoose: "Nhấn để chọn tệp",
    extractPreview: "Trích xuất & xem trước",
    extractedPreview: "Xem trước văn bản trích xuất",
    looksGood: "Ổn rồi — tiếp tục",
    approveForChatbot: "Duyệt cho chatbot",
    fTitle: "Tiêu đề",
    fSource: "Nguồn",
    fType: "Loại",
    approveHint:
      "Duyệt sẽ lập chỉ mục nguồn này vào kho vector để chatbot có thể trích dẫn.",
    indexing: "Đang lập chỉ mục…",
    approveIndex: "Duyệt & lập chỉ mục",
    indexedTitle: "Đã lập chỉ mục vào kho tri thức",
    indexedResult: (docs, chunks, skipped) =>
      `Đã xử lý ${docs} tài liệu · lập chỉ mục ${chunks} đoạn · bỏ qua ${skipped}.`,
    addAnother: "Thêm nguồn khác",
    viewSources: "Xem nguồn",
    indexFailed: "Lập chỉ mục thất bại. Kiểm tra backend.",

    totalQuestions7d: "Tổng câu hỏi (7 ngày)",
    avgConfidence: "Độ tin cậy trung bình",
    questionsPerDay: "Câu hỏi mỗi ngày",
    verified: "Đã xác minh",
    unanswered: "Chưa trả lời",
    topTopics: "Chủ đề hàng đầu",

    recentEvents: "Sự kiện hệ thống gần đây",
    colTime: "Thời gian",
    colLevel: "Mức độ",
    colMessage: "Nội dung",
    colSource: "Nguồn",
    logsNote:
      "Nguồn demo. Backend đã phát log có cấu trúc (request ID qua core/observability); nối GET /admin/logs để truyền về đây.",

    filters: { all: "Tất cả", new: "Mới", in_review: "Đang xem xét", forwarded: "Đã chuyển", resolved: "Đã giải quyết" },
    inbox: "Hộp thư",
    nothingHere: "Không có gì ở đây",
    noMatch: "Không có câu hỏi nào khớp bộ lọc này.",
    colQuestion: "Câu hỏi",
    colReason: "Lý do",
    colDepartment: "Phòng ban",
    colPriority: "Ưu tiên",
    colAsked: "Số lần hỏi",
    colCreated: "Tạo lúc",
    resolve: "Giải quyết",

    backToInbox: "← Về hộp thư",
    notFound: "Không tìm thấy câu hỏi",
    notFoundDesc: "Có thể nó đã được giải quyết hoặc đã bị xóa.",
    priorityLabel: (priority) => `ưu tiên ${priority}`,
    studentContext: "Bối cảnh sinh viên (ẩn danh)",
    suggestedDept: "Phòng ban đề xuất",
    firstAsked: "Hỏi lần đầu",
    createAnswer: "Tạo câu trả lời chính thức",
    answerPlaceholder: "Viết câu trả lời đã xác minh, trích dẫn chính sách chính thức…",
    addToKb: "Thêm câu trả lời này vào kho tri thức",
    publishing: "Đang đăng…",
    publishAnswer: "Đăng câu trả lời chính thức",
    routeOrAttach: "Chuyển hoặc đính kèm",
    forwardToDept: "Chuyển đến phòng ban",
    forward: "Chuyển",
    attachSource: "Đính kèm nguồn chính thức",
    attach: "Đính kèm",
    markResolved: "✓ Đánh dấu đã giải quyết",
    actionFailed: "Thao tác thất bại. Thử lại nhé.",
    publishedKb: "Đã đăng câu trả lời chính thức và thêm vào kho tri thức.",
    published: "Đã đăng câu trả lời chính thức.",
    forwardedTo: (dept) => `Đã chuyển đến ${dept}.`,
    sourceAttached: "Đã đính kèm nguồn vào câu hỏi này.",
    markedResolved: "Đã đánh dấu là đã giải quyết.",
  },

  dayFull: {
    Mon: "Thứ Hai",
    Tue: "Thứ Ba",
    Wed: "Thứ Tư",
    Thu: "Thứ Năm",
    Fri: "Thứ Sáu",
    Sat: "Thứ Bảy",
    Sun: "Chủ Nhật",
  },

  forum: {
    title: "Diễn đàn thảo luận",
    subtitle: "Hỏi, chia sẻ và thảo luận cùng cộng đồng sinh viên VinUni.",
    newTopic: "Tạo chủ đề",
    allCategories: "Tất cả chủ đề",
    sortActive: "Hoạt động",
    sortNew: "Mới nhất",
    sortTop: "Nổi bật",
    searchPlaceholder: "Tìm kiếm thảo luận…",
    topicCount: (n) => `${n} chủ đề`,
    commentCount: (n) => `${n} bình luận`,
    viewCount: (n) => `${n} lượt xem`,
    by: "bởi",
    reply: "Trả lời",
    comment: "Bình luận",
    commentPlaceholder: "Thêm bình luận… dùng @ để nhắc tên ai đó",
    replyPlaceholder: "Viết trả lời… dùng @ để nhắc tên ai đó",
    postComment: "Đăng bình luận",
    postReply: "Đăng trả lời",
    cancel: "Hủy",
    posting: "Đang đăng…",
    pinned: "Đã ghim",
    locked: "Đã khóa",
    lockedNotice: "Chủ đề này đã bị khóa. Không thể thêm bình luận mới.",
    officialAnswer: "Câu trả lời chính thức",
    markOfficial: "Đánh dấu chính thức",
    unmarkOfficial: "Bỏ đánh dấu",
    pin: "Ghim",
    unpin: "Bỏ ghim",
    lock: "Khóa",
    unlock: "Mở khóa",
    delete: "Xóa",
    moderator: "Quản trị",
    you: "Bạn",
    report: "Báo cáo",
    reportTitle: "Báo cáo nội dung",
    reportReasonPlaceholder: "Cho quản trị viên biết vấn đề là gì…",
    submitReport: "Gửi báo cáo",
    reportedToast: "Cảm ơn — quản trị viên sẽ xem xét.",
    upvote: "Tán thành",
    downvote: "Phản đối",
    viewDiscussion: "Xem thảo luận",
    backToForum: "Quay lại diễn đàn",
    titleLabel: "Tiêu đề",
    titlePlaceholder: "Bạn muốn thảo luận điều gì?",
    categoryLabel: "Danh mục",
    contentLabel: "Nội dung",
    contentPlaceholder: "Chia sẻ chi tiết… dùng @ để nhắc tên ai đó",
    tagsLabel: "Thẻ",
    tagsPlaceholder: "Nhập thẻ và nhấn Enter",
    attachmentsLabel: "Liên kết",
    attachmentUrlPlaceholder: "https://…",
    attachmentLabelPlaceholder: "Nhãn (tùy chọn)",
    addLink: "Thêm liên kết",
    create: "Đăng chủ đề",
    creating: "Đang đăng…",
    mentionHint: "Gõ @ để nhắc tên thành viên",
    mentionNoResults: "Không tìm thấy thành viên",
    emptyTitle: "Chưa có thảo luận nào",
    emptyDesc: "Hãy là người đầu tiên bắt đầu cuộc trò chuyện.",
    noComments: "Chưa có bình luận — hãy bắt đầu thảo luận.",
    createError: "Không thể đăng. Vui lòng thử lại.",
    actionFailed: "Đã xảy ra lỗi. Vui lòng thử lại.",
    removed: "[đã xóa]",
  },

  enums: {
    deadlineKind: {
      assignment: "bài tập",
      exam: "thi",
      registration: "đăng ký",
      tuition: "học phí",
      administrative: "hành chính",
    },
    tuitionItemStatus: { paid: "đã đóng", due: "đến hạn", overdue: "quá hạn", upcoming: "sắp tới" },
    ticketStatus: {
      draft: "bản nháp",
      submitted: "đã gửi",
      open: "đang mở",
      in_review: "đang xem xét",
      in_progress: "đang xử lý",
      waiting_for_student: "chờ bạn phản hồi",
      waiting_on_student: "chờ sinh viên",
      resolved: "đã xử lý",
      closed: "đã đóng",
    },
    ticketPriority: { low: "thấp", medium: "trung bình", high: "cao", urgent: "khẩn cấp" },
    ticketCategory: {
      academic: "Học vụ",
      schedule: "Lịch học",
      student_services: "Dịch vụ sinh viên",
      technical: "Kỹ thuật",
      other: "Khác",
    },
    notificationType: {
      academic: "Học vụ",
      schedule: "Lịch học",
      deadline: "Hạn chót",
      event: "Sự kiện",
      student_services: "Dịch vụ sinh viên",
      system: "Hệ thống",
      forum: "Diễn đàn",
    },
    eventType: {
      class: "Lớp học",
      deadline: "Hạn chót",
      exam: "Thi",
      event: "Sự kiện",
      reminder: "Nhắc nhở",
    },
    sourceStatus: {
      indexed: "đã lập chỉ mục",
      crawling: "đang thu thập",
      failed: "thất bại",
      disabled: "đã tắt",
      pending: "chờ xử lý",
    },
    questionStatus: { new: "mới", in_review: "đang xem xét", forwarded: "đã chuyển", resolved: "đã giải quyết" },
    questionPriority: { low: "thấp", medium: "trung bình", high: "cao" },
    questionReason: {
      no_verified_source: "Không có nguồn xác minh",
      low_confidence: "Độ tin cậy thấp",
      out_of_scope: "Ngoài phạm vi",
      ambiguous: "Mơ hồ",
    },
    logLevel: { info: "thông tin", warn: "cảnh báo", error: "lỗi", success: "thành công" },
    category: {
      Academic: "Học vụ",
      Tuition: "Học phí",
      Events: "Sự kiện",
      "Student Services": "Dịch vụ sinh viên",
      Schedule: "Lịch học",
    },
    department: {
      "Office of the Registrar": "Phòng Đào tạo",
      "Student Financial Services": "Phòng Tài chính Sinh viên",
      "Office of Financial Aid": "Phòng Hỗ trợ Tài chính",
      "Student Affairs": "Phòng Công tác Sinh viên",
      "Academic Advising": "Cố vấn Học tập",
      "IT Help Desk": "Hỗ trợ CNTT",
    },
  },
};

export const PORTAL_STRINGS: Record<Lang, PortalStrings> = { en, vi };

export function usePortal(): { p: PortalStrings; lang: Lang } {
  const { lang } = useI18n();
  return { p: PORTAL_STRINGS[lang], lang };
}
