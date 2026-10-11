"use client";
// 250px sidebar with PROBE / REMEDIATION / MONITORING sections.
import Link from "next/link";
import { usePathname } from "next/navigation";

const SECTIONS: { heading: string; items: { href: string; label: string; icon: string }[] }[] = [
  {
    heading: "PROBE",
    items: [
      { href: "/", label: "Overview", icon: "grid" },
      { href: "/runs", label: "Test Runs", icon: "clock" },
      { href: "/probe-settings", label: "Probe Settings", icon: "gear" },
      { href: "/compliance", label: "Compliance", icon: "check" },
      { href: "/target-settings", label: "Target Settings", icon: "target" },
    ],
  },
  {
    heading: "REMEDIATION",
    items: [{ href: "/hardening", label: "Prompt Hardening", icon: "shield" }],
  },
  {
    heading: "MONITORING",
    items: [{ href: "/logs", label: "Log Analysis", icon: "activity" }],
  },
];

const ICON_PATHS: Record<string, string> = {
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  clock: "M12 22a10 10 0 100-20 10 10 0 000 20zM12 6v6l4 2",
  gear: "M12 15a3 3 0 100-6 3 3 0 000 6z",
  check: "M22 11.08V12a10 10 0 11-5.93-9.14M22 4L12 14.01l-3-3",
  target: "M12 22a10 10 0 100-20 10 10 0 000 20zM12 18a6 6 0 100-12 6 6 0 000 12zM12 14a2 2 0 100-4 2 2 0 000 4z",
  shield: "M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z",
  activity: "M22 12h-4l-3 9L9 3l-3 9H2",
};

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-[250px] shrink-0 bg-bg border-r border-border flex flex-col">
      <div className="px-5 py-5 border-b border-border">
        <span className="text-sm font-bold tracking-widest text-accent">PROMPTBREAKER AI</span>
      </div>
      <div className="flex-1 overflow-y-auto py-4">
        {SECTIONS.map((section) => (
          <div key={section.heading} className="mb-5">
            <div className="px-5 mb-2 text-[11px] font-semibold tracking-wider text-faint">
              {section.heading}
            </div>
            {section.items.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`mx-3 flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                    active
                      ? "bg-card text-text border border-border"
                      : "text-muted hover:text-text hover:bg-card/50"
                  }`}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d={ICON_PATHS[item.icon]} />
                  </svg>
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </div>
      <div className="px-5 py-4 border-t border-border text-[11px] text-faint leading-relaxed">
        © 2025 PromptBreaker AI
        <br />
        Version 1.0.0
      </div>
    </aside>
  );
}
