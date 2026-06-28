import Image from "next/image";
import copilotLogo from "@/logo/VinCopilot.png";
import vinnieLogo from "@/logo/Vinnie.png";

// Official brand marks for the VinUni Student Support ecosystem, served from the real artwork in
// /frontend/logo via next/image (which downsizes/optimizes the large source PNGs automatically —
// no extra deps). Both marks sit on a WHITE field, so their containers should be light tiles
// (see `.brand-logo-tile` in ah-polish.css). Same `{ size }` API as before, so every existing
// call site (login, top-nav brand, chat bubble, widget, welcome) re-themes from this one file.
//
//   LogoCopilot — "Student Copilot" product mark (navy V + rising red arrow).
//   LogoVinnie  — "Vinnie" mascot (smiling navy/red V companion).

type P = { size?: number; title?: string; className?: string };

export const LogoCopilot = ({ size = 28, title, className }: P) => (
  <Image
    src={copilotLogo}
    alt={title ?? ""}
    width={size}
    height={size}
    className={className}
    style={{ objectFit: "contain" }}
    aria-hidden={title ? undefined : true}
    draggable={false}
  />
);

export const LogoVinnie = ({ size = 28, title, className }: P) => (
  <Image
    src={vinnieLogo}
    alt={title ?? ""}
    width={size}
    height={size}
    className={className}
    style={{ objectFit: "contain" }}
    aria-hidden={title ? undefined : true}
    draggable={false}
  />
);
