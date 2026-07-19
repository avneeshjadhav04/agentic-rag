"use client";

import { useState } from "react";
import { useChatStore, useActiveMessages } from "@/store/chatStore";
import { useConfigStore } from "@/store/configStore";
import { streamChat } from "@/lib/api";
import ChatHeader from "./ChatHeader";
import ChatMessages from "./ChatMessages";
import ChatInput from "./ChatInput";
import AgentTrace from "./AgentTrace";

export default function Chat() {
  const { addMessage, appendToLastMessage, setLastMessageTrace, isStreaming, setStreaming } = useChatStore();
  const { chat, embedding, webSearchEnabled, temperature } = useConfigStore();
  const messages = useActiveMessages();
  const [activeTrace, setActiveTrace] = useState<any[] | null>(null);

  const sendMessage = async (question: string) => {
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

  return (
    <div className="flex h-full flex-col">
      <ChatHeader messageCount={messages.length} />
      <ChatMessages messages={messages} isStreaming={isStreaming} onViewTrace={setActiveTrace} />
      <ChatInput onSend={sendMessage} disabled={isStreaming} />
      {activeTrace && <AgentTrace trace={activeTrace} onClose={() => setActiveTrace(null)} />}
    </div>
  );
}
