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
  evaluations: {
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

export interface MetricResult {
  name: string;
  score: number;
  threshold: number;
  passed: boolean;
  reason: string;
}

export interface GoldenResult {
  input: string;
  expected_output?: string;
  actual_output: string;
  metrics: MetricResult[];
  passed: boolean;
}

export interface MetricAverage {
  name: string;
  avg_score: number;
  pass_rate: number;
}

export interface EvalSummary {
  total: number;
  passed: number;
  metric_averages: MetricAverage[];
  goldens: GoldenResult[];
  run_at: string;
}

export interface GoldenGenerationStage {
  stage: string;
  message: string;
}

export interface GoldenGenerationResult {
  count: number;
  path: string;
}
