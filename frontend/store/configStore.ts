import { ProviderField } from "@/types";
import { create } from "zustand";
import { persist } from "zustand/middleware";

const configStorage = {
  getItem: (name: string) => {
    const raw = localStorage.getItem(name);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed?.state) {
      if (!parsed.state.generation && parsed.state.chat) {
        parsed.state.generation = parsed.state.chat;
        delete parsed.state.chat;
      }
      if (!parsed.state.generation) parsed.state.generation = {} as ProviderField;
      if (!parsed.state.generation.apiKey) parsed.state.generation.apiKey = "";
      if (!parsed.state.evaluation) parsed.state.evaluation = {} as ProviderField;
      if (!parsed.state.evaluation.apiKey) parsed.state.evaluation.apiKey = "";
      if (!parsed.state.embedding) parsed.state.embedding = {} as ProviderField;
      if (!parsed.state.embedding.apiKey) parsed.state.embedding.apiKey = "";
    }
    return parsed;
  },
  setItem: (name: string, value: { state?: Record<string, unknown> }) => {
    const cloned = JSON.parse(JSON.stringify(value));
    if (cloned?.state?.generation) delete cloned.state.generation.apiKey;
    if (cloned?.state?.evaluation) delete cloned.state.evaluation.apiKey;
    if (cloned?.state?.embedding) delete cloned.state.embedding.apiKey;
    localStorage.setItem(name, JSON.stringify(cloned));
  },
  removeItem: (name: string) => localStorage.removeItem(name),
};

export const HARDCODED_GENERATION_DEFAULTS: ProviderField = {
  provider: "nvidia-nim",
  baseUrl: "https://integrate.api.nvidia.com/v1",
  model: "openai/gpt-oss-20b",
  apiKey: "",
};

export const HARDCODED_EVALUATION_DEFAULTS: ProviderField = {
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
  generation: ProviderField;
  evaluation: ProviderField;
  embedding: ProviderField;
  envGenerationApiKey: string;
  envEvalApiKey: string;
  envEmbedApiKey: string;
  webSearchEnabled: boolean;
  temperature: number;
  chunkSize: number;
  chunkOverlap: number;
  setGeneration: (generation: Partial<ProviderField>) => void;
  setEvaluation: (evaluation: Partial<ProviderField>) => void;
  setEmbedding: (embedding: Partial<ProviderField>) => void;
  setWebSearchEnabled: (enabled: boolean) => void;
  setTemperature: (temp: number) => void;
  setChunkSize: (size: number) => void;
  setChunkOverlap: (overlap: number) => void;
  setEnvGenerationApiKey: (key: string) => void;
  setEnvEvalApiKey: (key: string) => void;
  setEnvEmbedApiKey: (key: string) => void;
}

export const useConfigStore = create<ConfigState>()(
  persist(
    (set) => ({
      generation: { ...HARDCODED_GENERATION_DEFAULTS },
      evaluation: { ...HARDCODED_EVALUATION_DEFAULTS },
      embedding: { ...HARDCODED_EMBEDDING_DEFAULTS },
      envGenerationApiKey: "",
      envEvalApiKey: "",
      envEmbedApiKey: "",
      webSearchEnabled: true,
      temperature: 0.7,
      chunkSize: 1000,
      chunkOverlap: 200,
      setGeneration: (generation) => set((state) => ({ generation: { ...state.generation, ...generation } })),
      setEvaluation: (evaluation) => set((state) => ({ evaluation: { ...state.evaluation, ...evaluation } })),
      setEmbedding: (embedding) =>
        set((state) => ({ embedding: { ...state.embedding, ...embedding } })),
      setEnvGenerationApiKey: (key) => set({ envGenerationApiKey: key }),
      setEnvEvalApiKey: (key) => set({ envEvalApiKey: key }),
      setEnvEmbedApiKey: (key) => set({ envEmbedApiKey: key }),
      setWebSearchEnabled: (enabled) => set({ webSearchEnabled: enabled }),
      setTemperature: (temp) => set({ temperature: temp }),
      setChunkSize: (size) => set({ chunkSize: size }),
      setChunkOverlap: (overlap) => set({ chunkOverlap: overlap }),
    }),
    {
      name: "config-storage",
      storage: configStorage,
      partialize: ({ envGenerationApiKey, envEvalApiKey, envEmbedApiKey, setGeneration, setEvaluation, setEmbedding, setWebSearchEnabled, setTemperature, setChunkSize, setChunkOverlap, setEnvGenerationApiKey, setEnvEvalApiKey, setEnvEmbedApiKey, ...rest }) => rest,
    }
  )
);
