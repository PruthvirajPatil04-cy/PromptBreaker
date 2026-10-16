"use client";
// Topbar: engine health badge + avatar.
import { useEffect, useState } from "react";
import { health, USE_MOCK } from "@/lib/api";

export function Topbar() {
  const [status, setStatus] = useState<"checking" | "up" | "down">("checking");
  const [version, setVersion] = useState("");

  useEffect(() => {
    if (USE_MOCK) return;
    let alive = true;
    const probe = () =>
      health()
        .then((h) => {
          if (!alive) return;
          setStatus(h.ok ? "up" : "down");
          setVersion(h.version);
        })
        .catch(() => alive && setStatus("down"));
    probe();
    const t = setInterval(probe, 15000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const dot =
    status === "up" ? "#22C55E" : status === "down" ? "#EF4444" : "#8B8D93";

  return (
    <header className="h-14 shrink-0 border-b border-border flex items-center justify-end px-6 bg-bg">
      <div className="flex items-center gap-4">
        {!USE_MOCK && (
          <span
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border bg-card text-xs text-muted"
            title={version ? `engine v${version}` : "engine health"}
          >
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: dot }} />
            {status === "checking" ? "checking…" : status === "up" ? "engine online" : "engine offline"}
          </span>
        )}
        <div className="h-9 w-9 rounded-full bg-[#F5C9A5]" />
      </div>
    </header>
  );
}
