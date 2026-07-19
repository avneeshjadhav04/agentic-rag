"use client";

import { useState } from "react";
import { useChatStore } from "@/store/chatStore";
import { useConfigStore } from "@/store/configStore";
import { streamChat } from "@/lib/api";
import ChatHeader from "./ChatHeader";
import ChatMessages from "./ChatMessages";
import ChatInput from "./ChatInput";
import AgentTrace from "./AgentTrace";

export default function Chat() {
  const { messages, addMessage, appendToLastMessage, setLastMessageTrace, isStreaming, setStreaming } = useChatStore();
  const { chat, embedding, webSearchEnabled, temperature } = useConfigStore();
  const [activeTrace, setActiveTrace] = useState<any[] | null>(null);

  const sendMessage = async (question: string) => {
    addMessage({ role: "user", content: question });
    addMessage({ role: "assistant", content: "" });
    setStreaming(true);

    try {
      const generator = streamChat(question, chat, embedding, webSearchEnabled, temperature);
      let result = await generator.next();
      while (!result.done) {
        if (typeof result.value === "string") {
          appendToLastMessage(result.value);
        }
        result = await generator.next();
      }
      if (result.value && "trace" in result.value) {
        setLastMessageTrace(result.value.trace || []);
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
