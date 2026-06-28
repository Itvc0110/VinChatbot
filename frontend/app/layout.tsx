import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Hanken_Grotesk } from "next/font/google";
import { THEME_INIT_SCRIPT } from "@/lib/theme";
import { Providers } from "./providers";
import "./globals.css";
import "./portal.css";
import "./academic-horizon.css";
import "./ah-pages.css";
import "./ah-admin.css";
import "./ah-polish.css";

// Inter with the `vietnamese` subset so diacritics (ế, ữ, ợ, Đ…) render crisply.
const inter = Inter({
  subsets: ["latin", "latin-ext", "vietnamese"],
  display: "swap",
  variable: "--font-sans",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-mono",
});

// Hanken Grotesk — Academic Horizon headline face (DESIGN.md §2). Exposed as the CSS
// variable --ah-font-head and consumed by the Academic Horizon layer. Additive: the
// default body font stays Inter, so existing pages render unchanged.
const hankenGrotesk = Hanken_Grotesk({
  subsets: ["latin", "latin-ext", "vietnamese"],
  display: "swap",
  variable: "--ah-font-head",
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
const APP_NAME = "VinUni Student Copilot";
const APP_DESCRIPTION =
  "24/7 AI student support for VinUni — verified, source-cited answers about academics, schedules, deadlines, tuition, events and student services.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  applicationName: APP_NAME,
  title: { default: APP_NAME, template: `%s · ${APP_NAME}` },
  description: APP_DESCRIPTION,
  openGraph: {
    type: "website",
    siteName: APP_NAME,
    title: APP_NAME,
    description: APP_DESCRIPTION,
    locale: "vi_VN",
    alternateLocale: ["en_US"],
  },
  twitter: {
    card: "summary",
    title: APP_NAME,
    description: APP_DESCRIPTION,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="vi"
      className={`${inter.variable} ${mono.variable} ${hankenGrotesk.variable}`}
    >
      <head>
        {/* Apply the saved/OS theme before paint to avoid a flash of the wrong theme. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
