import { ProviderField } from "@/types";
import { create } from "zustand";

export interface ConfigState {
  chat: ProviderField;
  embedding: ProviderField;
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
}

export const useConfigStore = create<ConfigState>((set) => ({
  chat: {
    provider: "nvidia-nim",
    baseUrl: "https://integrate.api.nvidia.com/v1",
    model: "deepseek-ai/deepseek-v4-flash",
    apiKey: "",
  },
  embedding: {
    provider: "nvidia-nim",
    baseUrl: "https://integrate.api.nvidia.com/v1",
    model: "nvidia/nemotron-3-embed-1b",
    apiKey: "",
  },
  webSearchEnabled: false,
  temperature: 0.7,
  chunkSize: 1000,
  chunkOverlap: 200,
  setChat: (chat) => set((state) => ({ chat: { ...state.chat, ...chat } })),
  setEmbedding: (embedding) =>
    set((state) => ({ embedding: { ...state.embedding, ...embedding } })),
  setWebSearchEnabled: (enabled) => set({ webSearchEnabled: enabled }),
  setTemperature: (temp) => set({ temperature: temp }),
  setChunkSize: (size) => set({ chunkSize: size }),
  setChunkOverlap: (overlap) => set({ chunkOverlap: overlap }),
}));
