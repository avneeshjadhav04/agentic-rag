"use client";

import { useConfigStore, HARDCODED_GENERATION_DEFAULTS, HARDCODED_EVALUATION_DEFAULTS, HARDCODED_EMBEDDING_DEFAULTS } from "@/store/configStore";
import { ProviderField } from "@/types";
import { fetchDefaults } from "@/lib/api";
import { useEffect } from "react";
import { Loader2 } from "lucide-react";

export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const configLoaded = useConfigStore((s) => s.configLoaded);
  const setEnvGenerationApiKey = useConfigStore((s) => s.setEnvGenerationApiKey);
  const setEnvEvalApiKey = useConfigStore((s) => s.setEnvEvalApiKey);
  const setEnvEmbedApiKey = useConfigStore((s) => s.setEnvEmbedApiKey);
  const setGeneration = useConfigStore((s) => s.setGeneration);
  const setEvaluation = useConfigStore((s) => s.setEvaluation);
  const setEmbedding = useConfigStore((s) => s.setEmbedding);
  const setConfigLoaded = useConfigStore((s) => s.setConfigLoaded);

  useEffect(() => {
    let cancelled = false;
    let attempt = 0;
    const maxAttempts = 6;
    const delays = [0, 500, 1000, 2000, 3000, 5000];

    const tryFetch = () => {
      if (cancelled) return;
      fetchDefaults()
        .then((defaults) => {
          if (cancelled) return;
          setEnvGenerationApiKey(defaults.generation?.apiKey || "");
          setEnvEvalApiKey(defaults.evaluation?.apiKey || "");
          setEnvEmbedApiKey(defaults.embedding?.apiKey || "");

          const state = useConfigStore.getState();

          const applyIfUnchanged = (
            current: ProviderField,
            hardcoded: ProviderField,
            env: ProviderField
          ): Partial<ProviderField> => {
            const updates: Partial<ProviderField> = {};
            for (const key of Object.keys(hardcoded) as (keyof ProviderField)[]) {
              if (key === "apiKey") continue;
              if (current[key] === hardcoded[key] && env[key] !== undefined) {
                updates[key] = env[key];
              }
            }
            return updates;
          };

          const genUpdates = applyIfUnchanged(state.generation, HARDCODED_GENERATION_DEFAULTS, defaults.generation);
          const evalUpdates = applyIfUnchanged(state.evaluation, HARDCODED_EVALUATION_DEFAULTS, defaults.evaluation);
          const embedUpdates = applyIfUnchanged(state.embedding, HARDCODED_EMBEDDING_DEFAULTS, defaults.embedding);
          if (Object.keys(genUpdates).length) setGeneration(genUpdates);
          if (Object.keys(evalUpdates).length) setEvaluation(evalUpdates);
          if (Object.keys(embedUpdates).length) setEmbedding(embedUpdates);

          setConfigLoaded(true);
        })
        .catch(() => {
          if (cancelled) return;
          attempt += 1;
          if (attempt < maxAttempts) {
            setTimeout(tryFetch, delays[attempt]);
          } else {
            setConfigLoaded(true);
          }
        });
    };
    tryFetch();

    return () => { cancelled = true; };
  }, [setGeneration, setEvaluation, setEmbedding, setEnvGenerationApiKey, setEnvEvalApiKey, setEnvEmbedApiKey, setConfigLoaded]);

  if (!configLoaded) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="flex items-center gap-3 text-muted">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="font-mono text-[11px] uppercase tracking-widest">Loading…</span>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}