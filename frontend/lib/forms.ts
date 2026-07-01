import type { ChatResponse } from "./types";

// Detects an official VinUni form FILE (.pdf/.doc/.docx on a vinuni.edu.vn host) in an assistant answer,
// so the answer-action row can offer "Draft this form". Kept deterministic + dependency-free.
const FORM_FILE_URL = /https?:\/\/[^\s"'<>)\]]+?\.(?:pdf|docx?)(?:\?[^\s"'<>)\]]*)?/gi;
const VINUNI_HOST = /(^|\.)vinuni\.edu\.vn$/i;

export interface DetectedFormLink {
  url: string;
  title: string;
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

// Turn a form file URL into a human-ish title (from its filename) as a fallback when we have no better one.
function titleFromUrl(url: string): string {
  try {
    const name = decodeURIComponent(new URL(url).pathname.split("/").pop() || "");
    return name.replace(/\.(pdf|docx?)$/i, "").replace(/[-_]+/g, " ").trim() || "VinUni form";
  } catch {
    return "VinUni form";
  }
}

// Return the first official VinUni form-file link found in the answer text, or null. `title` prefers a
// nearby heading in the answer, else the filename.
export function findFormLink(response: ChatResponse | null | undefined): DetectedFormLink | null {
  const text = response?.answer;
  if (!text) return null;
  const matches = text.match(FORM_FILE_URL);
  if (!matches) return null;
  for (const raw of matches) {
    const url = raw.replace(/[.,);\]]+$/, "");
    if (VINUNI_HOST.test(hostOf(url))) {
      return { url, title: titleFromUrl(url) };
    }
  }
  return null;
}
