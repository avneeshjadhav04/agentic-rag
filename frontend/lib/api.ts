import { ProviderField } from "@/types";

// Use a relative base path so Next.js rewrites proxy requests to the backend.
export const API_BASE = "";

export async function fetchProviders(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/api/config/providers`);
  if (!res.ok) throw new Error("Failed to load providers");
  const data = await res.json();
  return data.providers || [];
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
  if (!res.ok) throw new Error("File ingestion failed");
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
  if (!res.ok) throw new Error("URL ingestion failed");
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

export async function* streamChat(
  question: string,
  chat: ProviderField,
  embedding: ProviderField,
  webSearchEnabled: boolean,
  temperature: number
): AsyncGenerator<string, { trace?: any[] } | null, unknown> {
  const form = new FormData();
  form.append("question", question);
  form.append("chat_provider", chat.provider);
  form.append("chat_base_url", chat.baseUrl);
  form.append("chat_model", chat.model);
  form.append("chat_api_key", chat.apiKey);
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
        yield data;
      } else if (line.trim() === "") {
        currentEvent = "";
      }
    }
  }

  return null;
}
