"use client";

import { useConfigStore, HARDCODED_CHAT_DEFAULTS, HARDCODED_EMBEDDING_DEFAULTS } from "@/store/configStore";
import { ProviderField, ProviderPreset } from "@/types";
import { fetchDefaults, fetchProviders } from "@/lib/api";
import { useEffect, useState } from "react";
import { Eye, EyeOff } from "lucide-react";

const DEFAULT_PRESETS: ProviderPreset[] = [
  {
    id: "nvidia-nim",
    name: "NVIDIA NIM",
    chat: { base_url: "https://integrate.api.nvidia.com/v1", default_model: "openai/gpt-oss-20b" },
    embeddings: { base_url: "https://integrate.api.nvidia.com/v1", default_model: "nvidia/nemotron-3-embed-1b" },
  },
  {
    id: "openai",
    name: "OpenAI",
    chat: { base_url: "https://api.openai.com/v1", default_model: "gpt-4o-mini" },
    embeddings: { base_url: "https://api.openai.com/v1", default_model: "text-embedding-3-small" },
  },
  {
    id: "ollama",
    name: "Ollama",
    chat: { base_url: "http://localhost:11434/v1", default_model: "llama3.1" },
    embeddings: { base_url: "http://localhost:11434/v1", default_model: "nomic-embed-text" },
  },
  {
    id: "custom",
    name: "Custom",
    chat: { base_url: "", default_model: "" },
    embeddings: { base_url: "", default_model: "" },
  },
];

const labelClass = "font-mono text-[10px] uppercase tracking-widest text-muted";
const inputClass =
  "w-full bg-panel border border-line rounded-none px-3 py-2 text-sm text-text placeholder-muted transition";

export default function ProviderConfig() {
  const { chat, embedding, setChat, setEmbedding, setWebSearchEnabled, webSearchEnabled, temperature, setTemperature, chunkSize, chunkOverlap, setChunkSize, setChunkOverlap } =
    useConfigStore();
  const [presets, setPresets] = useState<ProviderPreset[]>(DEFAULT_PRESETS);
  const [showChatKey, setShowChatKey] = useState(false);
  const [showEmbedKey, setShowEmbedKey] = useState(false);
  const [envChatApiKey, setEnvChatApiKey] = useState<string | null>(null);
  const [envEmbedApiKey, setEnvEmbedApiKey] = useState<string | null>(null);

  useEffect(() => {
    fetchProviders()
      .then((data) => {
        if (data && data.length) setPresets(data);
      })
      .catch(() => {});

    fetchDefaults()
      .then((defaults) => {
        setEnvChatApiKey(defaults.chat.apiKey || null);
        setEnvEmbedApiKey(defaults.embedding.apiKey || null);

        const state = useConfigStore.getState();

        const applyIfUnchanged = (
          current: ProviderField,
          hardcoded: ProviderField,
          env: ProviderField
        ): Partial<ProviderField> => {
          const updates: Partial<ProviderField> = {};
          for (const key of Object.keys(hardcoded) as (keyof ProviderField)[]) {
            if (current[key] === hardcoded[key] && env[key] !== undefined) {
              updates[key] = env[key];
            }
          }
          return updates;
        };

        const chatUpdates = applyIfUnchanged(state.chat, HARDCODED_CHAT_DEFAULTS, defaults.chat);
        const embedUpdates = applyIfUnchanged(state.embedding, HARDCODED_EMBEDDING_DEFAULTS, defaults.embedding);
        if (Object.keys(chatUpdates).length) setChat(chatUpdates);
        if (Object.keys(embedUpdates).length) setEmbedding(embedUpdates);
      })
      .catch(() => {});
  }, [setChat, setEmbedding]);

  const applyChatPreset = (id: string) => {
    const preset = presets.find((p) => p.id === id);
    if (!preset) return;
    setChat({
      provider: id,
      baseUrl: preset.chat.base_url,
      model: preset.chat.default_model,
    });
  };

  const applyEmbedPreset = (id: string) => {
    const preset = presets.find((p) => p.id === id);
    if (!preset) return;
    setEmbedding({
      provider: id,
      baseUrl: preset.embeddings.base_url,
      model: preset.embeddings.default_model,
    });
  };

  return (
    <div className="space-y-8">
      {/* Chat provider */}
      <section className="space-y-3">
        <p className={labelClass}>Chat Provider</p>
        <select
          value={chat.provider}
          onChange={(e) => applyChatPreset(e.target.value)}
          className={inputClass}
        >
          {presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <input
          value={chat.baseUrl}
          onChange={(e) => setChat({ baseUrl: e.target.value })}
          placeholder="Base URL"
          className={inputClass}
        />
        <input
          value={chat.model}
          onChange={(e) => setChat({ model: e.target.value })}
          placeholder="Model Tag"
          className={inputClass}
        />
        <div className="relative">
          <input
            type={showChatKey ? "text" : "password"}
            value={chat.apiKey}
            onChange={(e) => setChat({ apiKey: e.target.value })}
            placeholder={envChatApiKey ? "Already set via env vars... paste new if needed" : "API Key"}
            className={`${inputClass} pr-8`}
          />
          <button
            type="button"
            onClick={() => setShowChatKey(!showChatKey)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-text"
          >
            {showChatKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      </section>

      {/* Embedding provider */}
      <section className="space-y-3">
        <p className={labelClass}>Embedding Provider</p>
        <select
          value={embedding.provider}
          onChange={(e) => applyEmbedPreset(e.target.value)}
          className={inputClass}
        >
          {presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <input
          value={embedding.baseUrl}
          onChange={(e) => setEmbedding({ baseUrl: e.target.value })}
          placeholder="Base URL"
          className={inputClass}
        />
        <input
          value={embedding.model}
          onChange={(e) => setEmbedding({ model: e.target.value })}
          placeholder="Model Tag"
          className={inputClass}
        />
        <div className="relative">
          <input
            type={showEmbedKey ? "text" : "password"}
            value={embedding.apiKey}
            onChange={(e) => setEmbedding({ apiKey: e.target.value })}
            placeholder={envEmbedApiKey ? "Already set via env vars... paste new if needed" : "API Key"}
            className={`${inputClass} pr-8`}
          />
          <button
            type="button"
            onClick={() => setShowEmbedKey(!showEmbedKey)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-text"
          >
            {showEmbedKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      </section>

      {/* Temperature */}
      <section className="space-y-2">
        <p className={labelClass}>
          Temperature <span className="text-text">{temperature}</span>
        </p>
        <input
          type="range"
          min={0}
          max={1}
          step={0.1}
          value={temperature}
          onChange={(e) => setTemperature(parseFloat(e.target.value))}
          style={{ '--pct': `${temperature * 100}%` } as React.CSSProperties}
          className="w-full"
        />
      </section>

      {/* Chunk settings */}
      <section className="space-y-2">
        <p className={labelClass}>Chunk Settings</p>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className={labelClass}>Chunk Size</label>
            <input
              type="number"
              value={chunkSize}
              onChange={(e) => setChunkSize(parseInt(e.target.value) || 1000)}
              className={inputClass}
            />
          </div>
          <div className="space-y-1.5">
            <label className={labelClass}>Overlap</label>
            <input
              type="number"
              value={chunkOverlap}
              onChange={(e) => setChunkOverlap(parseInt(e.target.value) || 200)}
              className={inputClass}
            />
          </div>
        </div>
      </section>
    </div>
  );
}