// Small, consistent stroke-icon set used across the portal shell + screens.
// 1.8 stroke, round caps — matches the existing Header icons.

type P = { size?: number };

const base = (size: number) => ({
  viewBox: "0 0 24 24",
  width: size,
  height: size,
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
});

export const IconGrid = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
  </svg>
);

export const IconChat = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M21 11.5a8.4 8.4 0 0 1-8.5 8.5 8.6 8.6 0 0 1-3.9-.9L3 21l1.9-5.6a8.4 8.4 0 0 1-.9-3.9A8.4 8.4 0 0 1 12.5 3 8.4 8.4 0 0 1 21 11.5z" />
  </svg>
);

export const IconCalendar = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <rect x="3" y="4" width="18" height="17" rx="2" />
    <path d="M3 9h18M8 2v4M16 2v4" />
  </svg>
);

export const IconWallet = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M3 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2" />
    <rect x="3" y="7" width="18" height="13" rx="2" />
    <path d="M16 13h.01" />
  </svg>
);

export const IconTicket = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4z" />
    <path d="M13 6v12" strokeDasharray="2 3" />
  </svg>
);

export const IconForum = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M8 10h7M8 13h4" />
    <path d="M4 5h12a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H9l-4 3v-3H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z" />
    <path d="M18 9h2a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2h-1v2l-2-2" />
  </svg>
);

export const IconShield = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M12 3l7 3v5c0 4.4-3 8.3-7 9.5C8 19.3 5 15.4 5 11V6z" />
    <path d="M9.5 12l1.8 1.8L15 10" />
  </svg>
);

export const IconDatabase = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <ellipse cx="12" cy="5" rx="8" ry="3" />
    <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
  </svg>
);

export const IconUpload = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
    <path d="M12 15V3M7 8l5-5 5 5" />
  </svg>
);

export const IconInbox = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M4 13l2.5-8h11L20 13" />
    <path d="M4 13h5l1 3h4l1-3h5v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" />
  </svg>
);

export const IconChart = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
  </svg>
);

export const IconClock = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);

export const IconAlert = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    <path d="M12 9v4M12 17h.01" />
  </svg>
);

export const IconBell = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.7 21a2 2 0 0 1-3.4 0" />
  </svg>
);

export const IconCheck = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M20 6L9 17l-5-5" />
  </svg>
);

export const IconExternal = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    <path d="M15 3h6v6M10 14 21 3" />
  </svg>
);

export const IconArrow = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

export const IconCap = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M22 9 12 5 2 9l10 4 10-4Z" />
    <path d="M6 11.3V16c0 1.1 2.7 2.8 6 2.8s6-1.7 6-2.8v-4.7" />
    <path d="M22 9v4.5" />
  </svg>
);

export const IconCog = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </svg>
);

export const IconSliders = ({ size = 18 }: P) => (
  <svg {...base(size)}>
    <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" />
  </svg>
);
