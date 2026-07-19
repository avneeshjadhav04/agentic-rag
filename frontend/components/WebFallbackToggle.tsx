"use client";

import { useConfigStore } from "@/store/configStore";

export default function WebFallbackToggle() {
  const { webSearchEnabled, setWebSearchEnabled } = useConfigStore();

  return (
    <section className="flex items-center justify-between">
      <div className="space-y-1">
        <p className="text-sm text-text">Web Fetch Fallback</p>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
          Propose &amp; fetch URLs when docs are irrelevant
        </p>
      </div>
      <button
        onClick={() => setWebSearchEnabled(!webSearchEnabled)}
        aria-pressed={webSearchEnabled}
        className={`w-5 h-5 border transition ${
          webSearchEnabled ? "bg-accent border-accent" : "bg-transparent border-line"
        }`}
      />
    </section>
  );
}
