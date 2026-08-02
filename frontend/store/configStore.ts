import { ProviderField } from "@/types";
import { create } from "zustand";
import { persist } from "zustand/middleware";

const HARDCODED_GENERATION_DEFAULTS: ProviderField = {
  provider: "nvidia-nim",
  baseUrl: "https://integrate.api.nvidia.com/v1",
  model: "openai/gpt-oss-20b",
  apiKey: "",
};

const HARDCODED_EVALUATION_DEFAULTS: ProviderField = {
  provider: "nvidia-nim",
  baseUrl: "https://integrate.api.nvidia.com/v1",
  model: "openai/gpt-oss-20b",
  apiKey: "",
};

const HARDCODED_EMBEDDING_DEFAULTS: ProviderField = {
  provider: "nvidia-nim",
  baseUrl: "https://integrate.api.nvidia.com/v1",
  model: "nvidia/nemotron-3-embed-1b",
  apiKey: "",
};

function mergeDefaults(stored: any, hardcoded: ProviderField): ProviderField {
  if (!stored || typeof stored !== "object") return { ...hardcoded };
  return {
    provider: stored.provider || hardcoded.provider,
    baseUrl: stored.baseUrl || hardcoded.baseUrl,
    model: stored.model || hardcoded.model,
    apiKey: stored.apiKey || "",
  };
}

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
      parsed.state.generation = mergeDefaults(parsed.state.generation, HARDCODED_GENERATION_DEFAULTS);
      parsed.state.evaluation = mergeDefaults(parsed.state.evaluation, HARDCODED_EVALUATION_DEFAULTS);
      parsed.state.embedding = mergeDefaults(parsed.state.embedding, HARDCODED_EMBEDDING_DEFAULTS);
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

export { HARDCODED_GENERATION_DEFAULTS, HARDCODED_EVALUATION_DEFAULTS, HARDCODED_EMBEDDING_DEFAULTS };

export interface ConfigState {
  generation: ProviderField;
  evaluation: ProviderField;
  embedding: ProviderField;
  envGenerationApiKey: string;
  envEvalApiKey: string;
  envEmbedApiKey: string;
  configLoaded: boolean;
  webSearchEnabled: boolean;
  temperature: number;
  chunkSize: number;
  chunkOverlap: number;
  sourcesCount: number;
  setGeneration: (generation: Partial<ProviderField>) => void;
  setEvaluation: (evaluation: Partial<ProviderField>) => void;
  setEmbedding: (embedding: Partial<ProviderField>) => void;
  setWebSearchEnabled: (enabled: boolean) => void;
  setTemperature: (temp: number) => void;
  setChunkSize: (size: number) => void;
  setChunkOverlap: (overlap: number) => void;
  setSourcesCount: (n: number) => void;
  setEnvGenerationApiKey: (key: string) => void;
  setEnvEvalApiKey: (key: string) => void;
  setEnvEmbedApiKey: (key: string) => void;
  setConfigLoaded: (loaded: boolean) => void;
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
      configLoaded: false,
      webSearchEnabled: true,
      temperature: 0.7,
      chunkSize: 1000,
      chunkOverlap: 200,
      sourcesCount: 0,
      setGeneration: (generation) => set((state) => ({ generation: { ...state.generation, ...generation } })),
      setEvaluation: (evaluation) => set((state) => ({ evaluation: { ...state.evaluation, ...evaluation } })),
      setEmbedding: (embedding) =>
        set((state) => ({ embedding: { ...state.embedding, ...embedding } })),
      setEnvGenerationApiKey: (key) => set({ envGenerationApiKey: key }),
      setEnvEvalApiKey: (key) => set({ envEvalApiKey: key }),
      setEnvEmbedApiKey: (key) => set({ envEmbedApiKey: key }),
      setConfigLoaded: (loaded) => set({ configLoaded: loaded }),
      setWebSearchEnabled: (enabled) => set({ webSearchEnabled: enabled }),
      setTemperature: (temp) => set({ temperature: temp }),
      setChunkSize: (size) => set({ chunkSize: size }),
      setChunkOverlap: (overlap) => set({ chunkOverlap: overlap }),
      setSourcesCount: (n) => set({ sourcesCount: n }),
    }),
    {
      name: "config-storage",
      storage: configStorage,
      partialize: ({ envGenerationApiKey, envEvalApiKey, envEmbedApiKey, configLoaded, sourcesCount, setGeneration, setEvaluation, setEmbedding, setWebSearchEnabled, setTemperature, setChunkSize, setChunkOverlap, setSourcesCount, setEnvGenerationApiKey, setEnvEvalApiKey, setEnvEmbedApiKey, setConfigLoaded, ...rest }) => rest,
    }
  )
);
