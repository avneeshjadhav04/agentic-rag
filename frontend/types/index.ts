export interface ProviderField {
  provider: string;
  baseUrl: string;
  model: string;
  apiKey: string;
}

export interface ProviderPreset {
  id: string;
  name: string;
  chat: {
    base_url: string;
    default_model: string;
  };
  embeddings: {
    base_url: string;
    default_model: string;
  };
}

export interface TraceStep {
  step: string;
  [key: string]: any;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  trace?: TraceStep[];
}

export interface SourceInfo {
  source_id: string;
  name: string;
}
