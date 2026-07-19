"use client";

interface ChatHeaderProps {
  messageCount: number;
}

export default function ChatHeader({ messageCount }: ChatHeaderProps) {
  const status =
    messageCount === 0
      ? "Ready"
      : `${messageCount} message${messageCount === 1 ? "" : "s"}`;

  return (
    <div className="flex items-center gap-3 px-8 py-5 border-b border-line">
      <div>
        <h2 className="text-base font-semibold tracking-tighter text-text">Agentic Chat</h2>
        <p className="font-mono text-[11px] uppercase tracking-widest text-muted mt-0.5">
          {status}
        </p>
      </div>
    </div>
  );
}