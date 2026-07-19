"use client";

import { useState } from "react";
import {
  PanelRightClose,
  MessageSquarePlus,
  Trash2,
  ChevronDown,
  ChevronRight,
  Settings,
  FileUp,
  History,
} from "lucide-react";
import { useChatStore } from "@/store/chatStore";
import { cn } from "@/lib/cn";
import ProviderConfig from "./ProviderConfig";
import IngestionPanel from "./IngestionPanel";

interface SidebarProps {
  open: boolean;
  onToggle: () => void;
}

export default function Sidebar({ open, onToggle }: SidebarProps) {
  const { conversations, activeConversationId, newChat, switchConversation, deleteConversation } = useChatStore();
  const [sections, setSections] = useState({ conversations: true, config: true, ingestion: true });

  const toggleSection = (key: keyof typeof sections) =>
    setSections((prev) => ({ ...prev, [key]: !prev[key] }));

  const formatDate = (ts: number) => {
    const d = new Date(ts);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  };

  return (
    <aside
      className={cn(
        "flex-shrink-0 flex flex-col border-r border-border bg-surface transition-all duration-300",
        open ? "w-96" : "w-0 overflow-hidden"
      )}
    >
      <div className="flex items-center justify-between p-6 border-b border-border">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-primary truncate">Agentic RAG</h1>
          <p className="text-xs text-muted">Multi-agent retrieval system</p>
        </div>
        <button
          onClick={onToggle}
          className="p-2 rounded-lg bg-panel border border-border hover:border-primary transition shrink-0"
        >
          <PanelRightClose className="w-5 h-5 text-primary" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Conversations */}
        <div>
          <button
            onClick={() => toggleSection("conversations")}
            className="flex items-center gap-2 w-full text-left text-sm font-semibold text-muted hover:text-text transition py-2"
          >
            {sections.conversations ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
            <History className="w-4 h-4" />
            Conversations
          </button>
          {sections.conversations && (
            <div className="mt-2 space-y-1">
              <button
                onClick={newChat}
                className="flex items-center gap-2 w-full px-3 py-2 text-sm text-text hover:bg-panel rounded-lg transition"
              >
                <MessageSquarePlus className="w-4 h-4 text-primary" />
                New Chat
              </button>
              {conversations.length === 0 && (
                <p className="px-3 py-2 text-xs text-muted">No conversations yet</p>
              )}
              {conversations.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => switchConversation(conv.id)}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition group",
                    conv.id === activeConversationId
                      ? "bg-panel border border-border"
                      : "hover:bg-panel"
                  )}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-text truncate">{conv.title}</p>
                    <p className="text-xs text-muted">{formatDate(conv.createdAt)}</p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteConversation(conv.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Configuration */}
        <div>
          <button
            onClick={() => toggleSection("config")}
            className="flex items-center gap-2 w-full text-left text-sm font-semibold text-muted hover:text-text transition py-2"
          >
            {sections.config ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
            <Settings className="w-4 h-4" />
            Configuration
          </button>
          {sections.config && (
            <div className="mt-2">
              <ProviderConfig />
            </div>
          )}
        </div>

        {/* Ingestion */}
        <div>
          <button
            onClick={() => toggleSection("ingestion")}
            className="flex items-center gap-2 w-full text-left text-sm font-semibold text-muted hover:text-text transition py-2"
          >
            {sections.ingestion ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
            <FileUp className="w-4 h-4" />
            Ingestion
          </button>
          {sections.ingestion && (
            <div className="mt-2">
              <IngestionPanel />
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
