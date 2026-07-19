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
        role="switch"
        aria-checked={webSearchEnabled}
        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
          webSearchEnabled ? "bg-accent" : "bg-line"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            webSearchEnabled ? "translate-x-[18px]" : "translate-x-[2px]"
          }`}
        />
      </button>
    </section>
  );
}
