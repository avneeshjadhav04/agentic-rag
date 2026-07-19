import { ChatMessage } from "@/types";
import { create } from "zustand";

export interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  addMessage: (message: ChatMessage) => void;
  appendToLastMessage: (content: string) => void;
  setLastMessageTrace: (trace: any[]) => void;
  setStreaming: (streaming: boolean) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>()((set) => ({
  messages: [],
  isStreaming: false,

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

  clearMessages: () => set({ messages: [] }),
}));
