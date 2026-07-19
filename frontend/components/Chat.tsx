"use client";

import { useChatStore } from "@/store/chatStore";
import { useConfigStore } from "@/store/configStore";
import { streamChat } from "@/lib/api";
import ChatHeader from "./ChatHeader";
import ChatMessages from "./ChatMessages";
import ChatInput from "./ChatInput";

export default function Chat() {
  const { messages, addMessage, appendToLastMessage, appendTraceStep, setLastMessageTrace, isStreaming, setStreaming } = useChatStore();
  const { chat, embedding, webSearchEnabled, temperature } = useConfigStore();

  const sendMessage = async (question: string) => {
    addMessage({ role: "user", content: question });
    addMessage({ role: "assistant", content: "" });
    setStreaming(true);

    try {
      const generator = streamChat(question, chat, embedding, webSearchEnabled, temperature);
      let result = await generator.next();
      while (!result.done) {
        const v = result.value;
        if (v.type === "token") {
          appendToLastMessage(v.value as string);
        } else if (v.type === "trace") {
          appendTraceStep(v.value);
          await new Promise(r => setTimeout(r, 500));
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
      <ChatMessages messages={messages} isStreaming={isStreaming} />
      <ChatInput onSend={sendMessage} disabled={isStreaming} />
    </div>
  );
}
