import { promises as fs } from "fs";
import path from "path";
import { NextResponse } from "next/server";

// Lightweight feedback sink for the "flag this answer" control. Appends one JSON line
// per report to a local file. No backend (Python) change — keeps the /chat contract and
// the hinge rule untouched. Swap this for a real endpoint/DB later.
const FEEDBACK_FILE = path.join(process.cwd(), ".feedback.jsonl");

export async function POST(req: Request) {
  let payload: unknown;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON" }, { status: 400 });
  }

  const body = payload as Record<string, unknown>;
  const record = {
    ts: new Date().toISOString(),
    conversation_id: typeof body.conversation_id === "string" ? body.conversation_id : null,
    message_id: typeof body.message_id === "string" ? body.message_id : null,
    reason: typeof body.reason === "string" ? body.reason.slice(0, 2000) : "",
    answer_excerpt: typeof body.answer_excerpt === "string" ? body.answer_excerpt.slice(0, 500) : "",
  };

  try {
    await fs.appendFile(FEEDBACK_FILE, JSON.stringify(record) + "\n", "utf8");
  } catch (err) {
    return NextResponse.json({ ok: false, error: "Could not store feedback" }, { status: 500 });
  }
  return NextResponse.json({ ok: true });
}
