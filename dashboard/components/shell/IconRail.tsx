"use client";
// Leftmost 60px icon rail — top logo, section icons, bottom utilities.
import Link from "next/link";
import { usePathname } from "next/navigation";

const ICONS: { href: string; label: string; d: string }[] = [
  { href: "/", label: "Overview", d: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z" },
  { href: "/target-settings", label: "Targets", d: "M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z" },
  { href: "/compliance", label: "Compliance", d: "M9 12l2 2 4-4M12 3a9 9 0 100 18 9 9 0 000-18z" },
  { href: "/logs", label: "Monitoring", d: "M3 12h4l3 8 4-16 3 8h4" },
  { href: "/probe-settings", label: "Settings", d: "M12 15a3 3 0 100-6 3 3 0 000 6z M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33h0a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51h0a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82v0a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z" },
];

const BOTTOM: { href: string; label: string; d: string }[] = [
  { href: "/probe-settings", label: "Grid", d: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3z" },
  { href: "/logs", label: "Chat", d: "M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" },
  { href: "/compliance", label: "Docs", d: "M4 19.5A2.5 2.5 0 016.5 17H20 M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" },
];

export function IconRail() {
  const pathname = usePathname();
  return (
    <nav className="w-[60px] shrink-0 bg-bg border-r border-border flex flex-col items-center py-4 gap-1">
      {/* logo */}
      <div className="mb-4 h-9 w-9 rounded-lg bg-accent flex items-center justify-center">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0A0A0B" strokeWidth="2.5">
          <path d="M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z" />
        </svg>
      </div>
      {ICONS.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href + item.label}
            href={item.href}
            title={item.label}
            className={`h-9 w-9 rounded-lg flex items-center justify-center transition-colors ${
              active ? "bg-accent/15 text-accent" : "text-muted hover:text-text hover:bg-card"
            }`}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d={item.d} />
            </svg>
          </Link>
        );
      })}
      <div className="mt-auto flex flex-col gap-1">
        {BOTTOM.map((item) => (
          <Link
            key={item.label}
            href={item.href}
            title={item.label}
            className="h-9 w-9 rounded-lg flex items-center justify-center text-faint hover:text-text hover:bg-card"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d={item.d} />
            </svg>
          </Link>
        ))}
      </div>
    </nav>
  );
}
