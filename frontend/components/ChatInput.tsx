"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { cn } from "@/lib/cn";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim() || disabled) return;
    onSend(input.trim());
    setInput("");
  };

  const inputClass =
    "flex-1 bg-panel border border-border rounded-xl px-4 py-3 text-sm text-text placeholder-muted focus:border-primary transition resize-none";

  return (
    <div className="px-8 py-5 border-t border-border bg-surface">
      <div className="flex gap-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          rows={2}
          placeholder="Ask anything..."
          disabled={disabled}
          className={cn(inputClass, disabled && "opacity-50")}
        />
        <button
          onClick={handleSend}
          disabled={disabled || !input.trim()}
          className="px-5 py-3 rounded-xl bg-primary text-white hover:bg-primary-dark transition disabled:opacity-50"
        >
          <Send className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
