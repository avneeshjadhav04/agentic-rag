import { ChatMessage } from "@/types";
import { create } from "zustand";

export interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  abortController: AbortController | null;
  addMessage: (message: ChatMessage) => void;
  appendToLastMessage: (content: string) => void;
  appendTraceStep: (step: any) => void;
  setLastMessageTrace: (trace: any[]) => void;
  setStreaming: (streaming: boolean) => void;
  setAbortController: (controller: AbortController | null) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>()((set) => ({
  messages: [],
  isStreaming: false,
  abortController: null,

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  appendToLastMessage: (content) =>
    set((state) => {
      const messages = [...state.messages];
      if (messages.length > 0 && messages[messages.length - 1].role === "assistant") {
        const last = { ...messages[messages.length - 1] };
        last.content += content;
        messages[messages.length - 1] = last;
      } else {
        messages.push({ role: "assistant", content });
      }
      return { messages };
    }),

  appendTraceStep: (step) =>
    set((state) => {
      const messages = [...state.messages];
      if (messages.length > 0 && messages[messages.length - 1].role === "assistant") {
        const last = { ...messages[messages.length - 1] };
        last.trace = [...(last.trace || []), step];
        messages[messages.length - 1] = last;
      }
      return { messages };
    }),

  setLastMessageTrace: (trace) =>
    set((state) => {
      const messages = [...state.messages];
      if (messages.length > 0 && messages[messages.length - 1].role === "assistant") {
        const last = { ...messages[messages.length - 1] };
        last.trace = trace;
        messages[messages.length - 1] = last;
      }
      return { messages };
    }),

  setStreaming: (streaming) => set({ isStreaming: streaming }),
  setAbortController: (controller) => set({ abortController: controller }),
  clearMessages: () => set({ messages: [] }),
}));
