"use client";

import { useChatStore } from "@/store/chatStore";
import { useConfigStore } from "@/store/configStore";
import { streamChat } from "@/lib/api";
import ChatHeader from "./ChatHeader";
import ChatMessages from "./ChatMessages";
import ChatInput from "./ChatInput";

interface ChatProps {
  onToggleSidebar?: () => void;
}

export default function Chat({ onToggleSidebar }: ChatProps) {
  const { messages, addMessage, appendToLastMessage, appendTraceStep, setLastMessageTrace, isStreaming, setStreaming, abortController, setAbortController } = useChatStore();
  const { generation, embedding, envGenerationApiKey, envEmbedApiKey, webSearchEnabled, temperature } = useConfigStore();

  const sendMessage = async (question: string) => {
    const history = messages;
    const effectiveGeneration = { ...generation, apiKey: generation.apiKey || envGenerationApiKey };
    const effectiveEmbedding = { ...embedding, apiKey: embedding.apiKey || envEmbedApiKey };
    addMessage({ role: "user", content: question });
    addMessage({ role: "assistant", content: "" });
    setStreaming(true);

    const controller = new AbortController();
    setAbortController(controller);

    try {
      const generator = streamChat(question, effectiveGeneration, effectiveEmbedding, webSearchEnabled, temperature, history, controller.signal);
      let result = await generator.next();
      while (!result.done) {
        const v = result.value;
        if (v.type === "token") {
          appendToLastMessage(v.value as string);
        } else if (v.type === "trace") {
          appendTraceStep(v.value);
        }
        result = await generator.next();
      }
      if (result.value?.trace) {
        setLastMessageTrace(result.value.trace);
      }
    } catch (e: any) {
      if (e.name === "AbortError") {
        appendToLastMessage("\n\n[Stopped]");
      } else {
        appendToLastMessage("\n\nError: " + (e.message || "Chat request failed"));
      }
    } finally {
      setAbortController(null);
      setStreaming(false);
    }
  };

  const handleStop = () => {
    if (abortController) {
      abortController.abort();
    }
  };

  return (
    <div className="flex h-full flex-col">
      <ChatHeader onToggleSidebar={onToggleSidebar} />
      <ChatMessages messages={messages} isStreaming={isStreaming} />
      <ChatInput onSend={sendMessage} onStop={handleStop} isStreaming={isStreaming} disabled={isStreaming} />
    </div>
  );
}