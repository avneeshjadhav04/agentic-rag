"use client";

import { useState } from "react";
import { ArrowUp, Square } from "lucide-react";
import { cn } from "@/lib/cn";

interface ChatInputProps {
  onSend: (text: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled: boolean;
}

export default function ChatInput({ onSend, onStop, isStreaming, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim() || disabled) return;
    onSend(input.trim());
    setInput("");
  };

  return (
    <div className="px-4 md:px-8 py-5">
      <div
        className={cn(
          "mx-auto max-w-full md:max-w-3xl flex items-center border border-line bg-panel",
          disabled && !isStreaming && "opacity-40"
        )}
      >
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
          placeholder="Message AI..."
          disabled={isStreaming}
          className="flex-1 bg-transparent px-4 py-3 text-sm text-text placeholder-muted resize-none focus:outline-none disabled:opacity-60"
        />
        {isStreaming ? (
          <button
            onClick={onStop}
            className="flex items-center justify-center rounded-sm w-10 h-10 mr-3 bg-accent text-background hover:bg-accent/80 transition"
            aria-label="Stop"
          >
            <Square className="w-4 h-4 fill-current" />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={disabled || !input.trim()}
            className="flex items-center justify-center rounded-sm w-10 h-10 mr-3 bg-accent text-background hover:bg-accent/80 transition disabled:opacity-40"
            aria-label="Send"
          >
            <ArrowUp className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}