"use client";

import { useChatStore } from "@/store/chatStore";
import { useConfigStore } from "@/store/configStore";
import { streamChat } from "@/lib/api";
import { useState } from "react";
import { Send, Bot, User, Activity } from "lucide-react";
import AgentTrace from "./AgentTrace";

export default function Chat() {
  const { messages, addMessage, appendToLastMessage, setLastMessageTrace, isStreaming, setStreaming } = useChatStore();
  const { chat, embedding, webSearchEnabled, temperature } = useConfigStore();
  const [input, setInput] = useState("");
  const [activeTrace, setActiveTrace] = useState<any[] | null>(null);

  const sendMessage = async () => {
    if (!input.trim() || isStreaming) return;
    const question = input.trim();
    setInput("");
    addMessage({ role: "user", content: question });
    addMessage({ role: "assistant", content: "" });
    setStreaming(true);

    try {
      const generator = streamChat(question, chat, embedding, webSearchEnabled, temperature);
      for await (const token of generator) {
        if (typeof token === "string") {
          appendToLastMessage(token);
        } else if (token && typeof token === "object" && "trace" in token) {
          setLastMessageTrace((token as { trace?: any[] }).trace || []);
        }
      }
    } catch (e: any) {
      appendToLastMessage("\n\nError: " + (e.message || "Chat request failed"));
    } finally {
      setStreaming(false);
    }
  };

  const inputClass =
    "flex-1 bg-panel border border-border rounded-xl px-4 py-3 text-sm text-text placeholder-muted focus:border-primary transition resize-none";

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-8 py-5 border-b border-border bg-surface">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            <Bot className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-text">Agentic Chat</h2>
            <p className="text-xs text-muted">Documents + agent reasoning + web fallback</p>
          </div>
        </div>
        {activeTrace ? (
          <button
            onClick={() => setActiveTrace(null)}
            className="text-xs text-primary hover:text-primary-light"
          >
            Close Trace
          </button>
        ) : null}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-muted">
            <Bot className="w-12 h-12 mb-4 opacity-30" />
            <p className="text-lg">Start a conversation</p>
            <p className="text-sm">Ingest documents or ask a question directly.</p>
          </div>
        )}
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-4 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-2xl px-5 py-4 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-primary text-white rounded-br-none"
                  : "bg-surface border border-border text-text rounded-bl-none"
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                {msg.role === "assistant" ? (
                  <Bot className="w-4 h-4 text-primary" />
                ) : (
                  <User className="w-4 h-4" />
                )}
                <span className="text-xs font-medium opacity-80">
                  {msg.role === "user" ? "You" : "Agent"}
                </span>
              </div>
              <div className="whitespace-pre-wrap">{msg.content || "Thinking..."}</div>
              {msg.role === "assistant" && msg.trace && msg.trace.length > 0 && (
                <button
                  onClick={() => setActiveTrace(msg.trace || null)}
                  className="mt-3 flex items-center gap-1 text-xs text-primary hover:text-primary-light"
                >
                  <Activity className="w-3 h-3" /> View agent trace
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="px-8 py-5 border-t border-border bg-surface">
        <div className="flex gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            rows={2}
            placeholder="Ask anything..."
            className={inputClass}
          />
          <button
            onClick={sendMessage}
            disabled={isStreaming || !input.trim()}
            className="px-5 py-3 rounded-xl bg-primary text-white hover:bg-primary-dark transition disabled:opacity-50"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Trace overlay */}
      {activeTrace && <AgentTrace trace={activeTrace} onClose={() => setActiveTrace(null)} />}
    </div>
  );
}
