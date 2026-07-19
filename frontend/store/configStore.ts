import { ProviderField } from "@/types";
import { create } from "zustand";
import { persist } from "zustand/middleware";

const configStorage = {
  getItem: (name: string) => {
    const raw = localStorage.getItem(name);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed?.state) {
      if (!parsed.state.chat) parsed.state.chat = {} as ProviderField;
      if (!parsed.state.chat.apiKey) parsed.state.chat.apiKey = "";
      if (!parsed.state.embedding) parsed.state.embedding = {} as ProviderField;
      if (!parsed.state.embedding.apiKey) parsed.state.embedding.apiKey = "";
    }
    return parsed;
  },
  setItem: (name: string, value: { state?: Record<string, unknown> }) => {
    const cloned = JSON.parse(JSON.stringify(value));
    if (cloned?.state?.chat) delete cloned.state.chat.apiKey;
    if (cloned?.state?.embedding) delete cloned.state.embedding.apiKey;
    localStorage.setItem(name, JSON.stringify(cloned));
  },
  removeItem: (name: string) => localStorage.removeItem(name),
};

export const HARDCODED_CHAT_DEFAULTS: ProviderField = {
  provider: "nvidia-nim",
  baseUrl: "https://integrate.api.nvidia.com/v1",
  model: "openai/gpt-oss-20b",
  apiKey: "",
};

export const HARDCODED_EMBEDDING_DEFAULTS: ProviderField = {
  provider: "nvidia-nim",
  baseUrl: "https://integrate.api.nvidia.com/v1",
  model: "nvidia/nemotron-3-embed-1b",
  apiKey: "",
};

export interface ConfigState {
  chat: ProviderField;
  embedding: ProviderField;
  envChatApiKey: string;
  envEmbedApiKey: string;
  webSearchEnabled: boolean;
  temperature: number;
  chunkSize: number;
  chunkOverlap: number;
  setChat: (chat: Partial<ProviderField>) => void;
  setEmbedding: (embedding: Partial<ProviderField>) => void;
  setWebSearchEnabled: (enabled: boolean) => void;
  setTemperature: (temp: number) => void;
  setChunkSize: (size: number) => void;
  setChunkOverlap: (overlap: number) => void;
  setEnvChatApiKey: (key: string) => void;
  setEnvEmbedApiKey: (key: string) => void;
}

export const useConfigStore = create<ConfigState>()(
  persist(
    (set) => ({
      chat: { ...HARDCODED_CHAT_DEFAULTS },
      embedding: { ...HARDCODED_EMBEDDING_DEFAULTS },
      envChatApiKey: "",
      envEmbedApiKey: "",
      webSearchEnabled: true,
      temperature: 0.7,
      chunkSize: 1000,
      chunkOverlap: 200,
      setChat: (chat) => set((state) => ({ chat: { ...state.chat, ...chat } })),
      setEmbedding: (embedding) =>
        set((state) => ({ embedding: { ...state.embedding, ...embedding } })),
      setEnvChatApiKey: (key) => set({ envChatApiKey: key }),
      setEnvEmbedApiKey: (key) => set({ envEmbedApiKey: key }),
      setWebSearchEnabled: (enabled) => set({ webSearchEnabled: enabled }),
      setTemperature: (temp) => set({ temperature: temp }),
      setChunkSize: (size) => set({ chunkSize: size }),
      setChunkOverlap: (overlap) => set({ chunkOverlap: overlap }),
    }),
    {
      name: "config-storage",
      storage: configStorage,
      partialize: ({ envChatApiKey, envEmbedApiKey, setEnvChatApiKey, setEnvEmbedApiKey, setChat, setEmbedding, setWebSearchEnabled, setTemperature, setChunkSize, setChunkOverlap, ...rest }) => rest,
    }
  )
);
