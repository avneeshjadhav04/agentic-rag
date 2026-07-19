"use client";

import { useConfigStore } from "@/store/configStore";
import { ProviderPreset } from "@/types";
import { fetchProviders } from "@/lib/api";
import { useEffect, useState } from "react";
import { Eye, EyeOff, Settings } from "lucide-react";

const DEFAULT_PRESETS: ProviderPreset[] = [
  {
    id: "nvidia-nim",
    name: "NVIDIA NIM",
    chat: { base_url: "https://integrate.api.nvidia.com/v1", default_model: "deepseek-ai/deepseek-v4-flash" },
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

export default function ProviderConfig() {
  const { chat, embedding, setChat, setEmbedding, setWebSearchEnabled, webSearchEnabled, temperature, setTemperature } =
    useConfigStore();
  const [presets, setPresets] = useState<ProviderPreset[]>(DEFAULT_PRESETS);
  const [showChatKey, setShowChatKey] = useState(false);
  const [showEmbedKey, setShowEmbedKey] = useState(false);

  useEffect(() => {
    fetchProviders()
      .then((data) => {
        if (data && data.length) setPresets(data);
      })
      .catch(() => {
        // Keep defaults on error.
      });
  }, []);

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

  const inputClass =
    "w-full bg-panel border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-muted focus:border-primary transition";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-primary">
        <Settings className="w-5 h-5" />
        <h2 className="text-lg font-semibold">Configuration</h2>
      </div>

      {/* Chat provider */}
      <section className="space-y-3">
        <p className="text-sm font-medium text-text">Chat Provider</p>
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
          placeholder="Model name"
          className={inputClass}
        />
        <div className="relative">
          <input
            type={showChatKey ? "text" : "password"}
            value={chat.apiKey}
            onChange={(e) => setChat({ apiKey: e.target.value })}
            placeholder="API Key"
            className={inputClass}
          />
          <button
            type="button"
            onClick={() => setShowChatKey(!showChatKey)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-primary"
          >
            {showChatKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      </section>

      {/* Embedding provider */}
      <section className="space-y-3">
        <p className="text-sm font-medium text-text">Embedding Provider</p>
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
          placeholder="Model name"
          className={inputClass}
        />
        <div className="relative">
          <input
            type={showEmbedKey ? "text" : "password"}
            value={embedding.apiKey}
            onChange={(e) => setEmbedding({ apiKey: e.target.value })}
            placeholder="API Key"
            className={inputClass}
          />
          <button
            type="button"
            onClick={() => setShowEmbedKey(!showEmbedKey)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-primary"
          >
            {showEmbedKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      </section>

      {/* Fallback toggle */}
      <section className="flex items-center justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-text">Web Fetch Fallback</p>
          <p className="text-xs text-muted">Propose &amp; fetch URLs when docs are irrelevant</p>
        </div>
        <button
          onClick={() => setWebSearchEnabled(!webSearchEnabled)}
          className={`relative w-11 h-6 rounded-full transition ${
            webSearchEnabled ? "bg-primary" : "bg-border"
          }`}
        >
          <span
            className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${
              webSearchEnabled ? "translate-x-5" : ""
            }`}
          />
        </button>
      </section>

      {/* Temperature */}
      <section className="space-y-2">
        <p className="text-sm font-medium text-text">Temperature: {temperature}</p>
        <input
          type="range"
          min={0}
          max={1}
          step={0.1}
          value={temperature}
          onChange={(e) => setTemperature(parseFloat(e.target.value))}
          className="w-full accent-primary"
        />
      </section>
    </div>
  );
}
