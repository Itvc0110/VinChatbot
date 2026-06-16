import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VinChatbot — Academic Q&A",
  description: "Source-grounded answers about VinUni academics and services.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
