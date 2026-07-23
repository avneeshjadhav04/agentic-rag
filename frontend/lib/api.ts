import { ProviderField, SourceInfo, EvalSummary, GoldenGenerationResult } from "@/types";

// Use a relative base path so Next.js rewrites proxy requests to the backend.
export const API_BASE = "";

export async function fetchProviders(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/api/config/providers`);
  if (!res.ok) throw new Error("Failed to load providers");
  const data = await res.json();
  return data.providers || [];
}

export async function fetchDefaults(): Promise<{generation: ProviderField; evaluation: ProviderField; embedding: ProviderField}> {
  const res = await fetch(`${API_BASE}/api/config/defaults`);
  if (!res.ok) throw new Error("Failed to load defaults");
  return res.json();
}

export async function ingestFiles(
  files: FileList,
  embedding: ProviderField,
  chunkSize: number,
  chunkOverlap: number
): Promise<any> {
  const form = new FormData();
  for (let i = 0; i < files.length; i++) {
    form.append("files", files[i]);
  }
  form.append("embed_base_url", embedding.baseUrl);
  form.append("embed_model", embedding.model);
  form.append("embed_api_key", embedding.apiKey);
  form.append("chunk_size", String(chunkSize));
  form.append("chunk_overlap", String(chunkOverlap));

  const res = await fetch(`${API_BASE}/api/ingest/files`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`File ingestion failed (${res.status}): ${body.slice(0, 200)}`);
  }
  return res.json();
}

export async function ingestUrls(
  urls: string,
  embedding: ProviderField,
  chunkSize: number,
  chunkOverlap: number
): Promise<any> {
  const form = new FormData();
  form.append("urls", urls);
  form.append("embed_base_url", embedding.baseUrl);
  form.append("embed_model", embedding.model);
  form.append("embed_api_key", embedding.apiKey);
  form.append("chunk_size", String(chunkSize));
  form.append("chunk_overlap", String(chunkOverlap));

  const res = await fetch(`${API_BASE}/api/ingest/urls`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`URL ingestion failed (${res.status}): ${body.slice(0, 200)}`);
  }
  return res.json();
}

export async function clearStore(embedding: ProviderField): Promise<any> {
  const form = new FormData();
  form.append("embed_base_url", embedding.baseUrl);
  form.append("embed_model", embedding.model);
  form.append("embed_api_key", embedding.apiKey);

  const res = await fetch(`${API_BASE}/api/ingest/clear`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error("Failed to clear store");
  return res.json();
}

export async function deleteSource(source_id: string, embedding: ProviderField): Promise<any> {
  const form = new FormData();
  form.append("source_id", source_id);
  form.append("embed_base_url", embedding.baseUrl);
  form.append("embed_model", embedding.model);
  form.append("embed_api_key", embedding.apiKey);

  const res = await fetch(`${API_BASE}/api/ingest/delete-source`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error("Failed to delete source");
  return res.json();
}

export async function listSources(embedding: ProviderField): Promise<SourceInfo[]> {
  const form = new FormData();
  form.append("embed_base_url", embedding.baseUrl);
  form.append("embed_model", embedding.model);
  form.append("embed_api_key", embedding.apiKey);

  const res = await fetch(`${API_BASE}/api/ingest/list`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.sources || [];
}

export async function* streamChat(
  question: string,
  generation: ProviderField,
  embedding: ProviderField,
  webSearchEnabled: boolean,
  temperature: number,
  messages: { role: string; content: string }[] = []
): AsyncGenerator<
  { type: "token" | "trace"; value: string | any },
  { trace?: any[] } | null,
  unknown
> {
  const form = new FormData();
  form.append("question", question);
  form.append("messages", JSON.stringify(messages));
  form.append("generation_provider", generation.provider);
  form.append("generation_base_url", generation.baseUrl);
  form.append("generation_model", generation.model);
  form.append("generation_api_key", generation.apiKey);
  form.append("embed_provider", embedding.provider);
  form.append("embed_base_url", embedding.baseUrl);
  form.append("embed_model", embedding.model);
  form.append("embed_api_key", embedding.apiKey);
  form.append("web_search_enabled", String(webSearchEnabled));
  form.append("temperature", String(temperature));

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);
  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    body: form,
    signal: controller.signal,
  });
  clearTimeout(timeout);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Chat request failed (${res.status}): ${body.slice(0, 200)}`);
  }
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.replace("event: ", "").trim();
      } else if (line.startsWith("data: ")) {
        const data = line.replace("data: ", "");
        if (currentEvent === "done") {
          try {
            const parsed = JSON.parse(data);
            return parsed;
          } catch {
            return null;
          }
        }
        if (currentEvent === "error") {
          try {
            const parsed = JSON.parse(data);
            throw new Error(parsed.message || "Chat request failed");
          } catch (e) {
            throw e;
          }
        }
        if (currentEvent === "trace") {
          yield { type: "trace", value: JSON.parse(data) };
        } else {
          try {
            yield { type: "token", value: JSON.parse(data) };
          } catch {
            yield { type: "token", value: data };
          }
        }
      } else if (line.trim() === "") {
        currentEvent = "";
      }
    }
  }

  return null;
}

export async function fetchEvalResults(): Promise<EvalSummary | null> {
  const res = await fetch(`${API_BASE}/api/eval/results`);
  if (!res.ok) return null;
  const data = await res.json();
  if (data.error) return null;
  return data as EvalSummary;
}

export async function* streamEvalRun(
  generation: ProviderField,
  evaluation: ProviderField,
  embedding: ProviderField
): AsyncGenerator<
  { type: "progress" | "done" | "error"; value: any },
  EvalSummary | null,
  unknown
> {
  const form = new FormData();
  form.append("generation_base_url", generation.baseUrl);
  form.append("generation_model", generation.model);
  form.append("generation_api_key", generation.apiKey);
  form.append("evaluation_base_url", evaluation.baseUrl);
  form.append("evaluation_model", evaluation.model);
  form.append("evaluation_api_key", evaluation.apiKey);
  form.append("embed_base_url", embedding.baseUrl);
  form.append("embed_model", embedding.model);
  form.append("embed_api_key", embedding.apiKey);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 600000);
  const res = await fetch(`${API_BASE}/api/eval/run`, {
    method: "POST",
    body: form,
    signal: controller.signal,
  });
  clearTimeout(timeout);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Eval run failed (${res.status}): ${body.slice(0, 200)}`);
  }
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.replace("event: ", "").trim();
      } else if (line.startsWith("data: ")) {
        const data = line.replace("data: ", "");
        if (currentEvent === "done") {
          try {
            const parsed = JSON.parse(data);
            return parsed as EvalSummary;
          } catch {
            return null;
          }
        }
        if (currentEvent === "error") {
          try {
            const parsed = JSON.parse(data);
            throw new Error(parsed.message || "Eval run failed");
          } catch (e) {
            throw e;
          }
        }
        if (currentEvent === "progress") {
          yield { type: "progress", value: JSON.parse(data) };
        }
      } else if (line.trim() === "") {
        currentEvent = "";
      }
    }
  }

  return null;
}

export async function* streamGenerateGoldens(
  evaluation: ProviderField,
  embedding: ProviderField
): AsyncGenerator<
  { type: "progress" | "done" | "error"; value: any },
  GoldenGenerationResult | null,
  unknown
> {
  const form = new FormData();
  form.append("evaluation_base_url", evaluation.baseUrl);
  form.append("evaluation_model", evaluation.model);
  form.append("evaluation_api_key", evaluation.apiKey);
  form.append("embed_base_url", embedding.baseUrl);
  form.append("embed_model", embedding.model);
  form.append("embed_api_key", embedding.apiKey);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 600000);
  const res = await fetch(`${API_BASE}/api/eval/generate-goldens`, {
    method: "POST",
    body: form,
    signal: controller.signal,
  });
  clearTimeout(timeout);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Golden generation failed (${res.status}): ${body.slice(0, 200)}`);
  }
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.replace("event: ", "").trim();
      } else if (line.startsWith("data: ")) {
        const data = line.replace("data: ", "");
        if (currentEvent === "done") {
          try {
            const parsed = JSON.parse(data);
            return parsed as GoldenGenerationResult;
          } catch {
            return null;
          }
        }
        if (currentEvent === "error") {
          try {
            const parsed = JSON.parse(data);
            throw new Error(parsed.message || "Golden generation failed");
          } catch (e) {
            throw e;
          }
        }
        if (currentEvent === "progress") {
          yield { type: "progress", value: JSON.parse(data) };
        }
      } else if (line.trim() === "") {
        currentEvent = "";
      }
    }
  }

  return null;
}
