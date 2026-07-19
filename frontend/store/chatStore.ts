import { ChatMessage, Conversation } from "@/types";
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  isStreaming: boolean;
  addMessage: (message: ChatMessage) => void;
  appendToLastMessage: (content: string) => void;
  setLastMessageTrace: (trace: any[]) => void;
  setStreaming: (streaming: boolean) => void;
  clearMessages: () => void;
  newChat: () => void;
  switchConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
}

const createNewConversation = (): Conversation => ({
  id: crypto.randomUUID(),
  title: "New Chat",
  messages: [],
  createdAt: Date.now(),
});

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      conversations: [createNewConversation()],
      activeConversationId: null,
      isStreaming: false,

      addMessage: (message) =>
        set((state) => {
          let activeId = state.activeConversationId;
          if (!activeId && state.conversations.length > 0) {
            activeId = state.conversations[0].id;
          }

          const idx = state.conversations.findIndex((c) => c.id === activeId);
          if (idx === -1) return state;

          const conv = state.conversations[idx];
          const newMessages = [...conv.messages, message];

          let title = conv.title;
          if (
            message.role === "user" &&
            title === "New Chat" &&
            newMessages.filter((m) => m.role === "user").length === 1
          ) {
            title =
              message.content.slice(0, 60) +
              (message.content.length > 60 ? "..." : "");
          }

          const newConversations = state.conversations.map((c, i) =>
            i === idx ? { ...c, messages: newMessages, title } : c
          );

          return { conversations: newConversations, activeConversationId: activeId };
        }),

      appendToLastMessage: (content) =>
        set((state) => {
          const idx = state.conversations.findIndex(
            (c) => c.id === state.activeConversationId
          );
          if (idx === -1) return state;

          const conv = state.conversations[idx];
          const messages = [...conv.messages];
          if (messages.length > 0 && messages[messages.length - 1].role === "assistant") {
            const last = { ...messages[messages.length - 1] };
            last.content += content;
            messages[messages.length - 1] = last;
          } else {
            messages.push({ role: "assistant", content });
          }

          const newConversations = state.conversations.map((c, i) =>
            i === idx ? { ...c, messages } : c
          );

          return { conversations: newConversations };
        }),

      setLastMessageTrace: (trace) =>
        set((state) => {
          const idx = state.conversations.findIndex(
            (c) => c.id === state.activeConversationId
          );
          if (idx === -1) return state;

          const conv = state.conversations[idx];
          const messages = [...conv.messages];
          if (messages.length > 0 && messages[messages.length - 1].role === "assistant") {
            const last = { ...messages[messages.length - 1] };
            last.trace = trace;
            messages[messages.length - 1] = last;
          }

          const newConversations = state.conversations.map((c, i) =>
            i === idx ? { ...c, messages } : c
          );

          return { conversations: newConversations };
        }),

      setStreaming: (streaming) => set({ isStreaming: streaming }),

      clearMessages: () =>
        set((state) => {
          const idx = state.conversations.findIndex(
            (c) => c.id === state.activeConversationId
          );
          if (idx === -1) return state;

          const newConversations = state.conversations.map((c, i) =>
            i === idx ? { ...c, messages: [], title: "New Chat" } : c
          );

          return { conversations: newConversations };
        }),

      newChat: () =>
        set((state) => {
          const newConv = createNewConversation();
          return {
            conversations: [...state.conversations, newConv],
            activeConversationId: newConv.id,
          };
        }),

      switchConversation: (id) => set({ activeConversationId: id }),

      deleteConversation: (id) =>
        set((state) => {
          const remaining = state.conversations.filter((c) => c.id !== id);
          if (remaining.length === 0) {
            const newConv = createNewConversation();
            return { conversations: [newConv], activeConversationId: newConv.id };
          }
          if (state.activeConversationId === id) {
            return { conversations: remaining, activeConversationId: remaining[0].id };
          }
          return { conversations: remaining };
        }),
    }),
    {
      name: "chat-storage",
      partialize: (state) => ({
        conversations: state.conversations,
        activeConversationId: state.activeConversationId,
      }),
      onRehydrateStorage: () => (state) => {
        if (
          state &&
          state.conversations.length > 0 &&
          !state.conversations.find((c) => c.id === state.activeConversationId)
        ) {
          state.activeConversationId = state.conversations[0].id;
        }
      },
    }
  )
);

export const useActiveMessages = () =>
  useChatStore(
    (s) =>
      s.conversations.find((c) => c.id === s.activeConversationId)?.messages ?? []
  );

export const useActiveTitle = () =>
  useChatStore(
    (s) =>
      s.conversations.find((c) => c.id === s.activeConversationId)?.title ?? "New Chat"
  );
