// The backend appends a canonical "Official sources to check:" markdown list to its
// refusal / couldn't-ground answers (see guardrails.py _source_list / OFFICIAL_SOURCES).
// We strip that trailing block out of the chat bubble and render it ONCE in the panel,
// so the route-to-office links live in a single place and never drift.

export interface OfficialRoute {
  title: string;
  url: string;
}

// Headings the backend emits (EN + VI). Match start-of-line, case-insensitive.
const HEADING_RE =
  /^(?:official sources to check:|nguồn chính thức nên tham khảo:)\s*$/i;
const LINK_RE = /^\s*-\s*\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)\s*$/;

export interface SplitAnswer {
  body: string;
  routes: OfficialRoute[];
}

export function splitOfficialSources(answer: string): SplitAnswer {
  const lines = answer.split("\n");
  let headingIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    if (HEADING_RE.test(lines[i].trim())) {
      headingIdx = i;
      break;
    }
  }
  if (headingIdx === -1) return { body: answer, routes: [] };

  const routes: OfficialRoute[] = [];
  for (let i = headingIdx + 1; i < lines.length; i++) {
    const m = lines[i].match(LINK_RE);
    if (m) {
      routes.push({ title: m[1], url: m[2] });
    } else if (lines[i].trim() !== "") {
      // A non-blank, non-link line ends the source block — keep it in the body.
      break;
    }
  }
  if (routes.length === 0) return { body: answer, routes: [] };

  // Body is everything before the heading, trailing blank lines trimmed.
  const body = lines.slice(0, headingIdx).join("\n").replace(/\s+$/, "");
  return { body, routes };
}
