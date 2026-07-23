"use client";

import { useConfigStore } from "@/store/configStore";
import { fetchEvalResults, fetchGoldensExist, streamEvalRun, streamGenerateGoldens } from "@/lib/api";
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Loader2, RefreshCw, Play, Plus, Minus, Copy, Check, Download, Sparkles } from "lucide-react";
import { EvalSummary, GoldenResult, MetricResult } from "@/types";

const labelClass = "font-mono text-[10px] uppercase tracking-widest text-muted";
const inputClass =
  "w-full bg-panel border border-line rounded-none px-3 py-2 text-sm text-text placeholder-muted transition";
const btnPrimary =
  "flex items-center justify-center gap-2 px-4 py-2 rounded-none bg-accent text-background font-mono text-[11px] uppercase tracking-widest hover:bg-accent/80 transition disabled:opacity-40";
const btnOutline =
  "flex items-center justify-center gap-2 w-full px-4 py-2 rounded-none border border-line text-muted font-mono text-[11px] uppercase tracking-widest hover:border-accent hover:text-text transition disabled:opacity-40";

const METRIC_LABELS: Record<string, string> = {
  AnswerRelevancyMetric: "Answer Relevancy",
  FaithfulnessMetric: "Faithfulness",
  ContextualPrecisionMetric: "Context Precision",
  ContextualRecallMetric: "Context Recall",
  ContextualRelevancyMetric: "Context Relevancy",
};

function scoreColor(passed: boolean): string {
  return passed ? "text-accent" : "text-muted";
}

function GoldenRow({ golden, index }: { golden: GoldenResult; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const copyGolden = () => {
    navigator.clipboard.writeText(JSON.stringify(golden, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const fieldBlock = (label: string, value: string) => (
    <div>
      <p className={labelClass}>{label}</p>
      <p className="font-mono text-[11px] text-text whitespace-pre-wrap leading-relaxed mt-1">
        {value}
      </p>
    </div>
  );

  const passedCount = golden.metrics.filter((m) => m.passed).length;
  const totalMetrics = golden.metrics.length;

  return (
    <div className="border-b border-line last:border-b-0">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left"
      >
        <span className={scoreColor(golden.passed) + " font-mono text-[11px] leading-none flex-shrink-0"}>
          {golden.passed ? "✓" : "×"}
        </span>
        <span className="font-mono text-[11px] text-text truncate flex-1" title={golden.input}>
          {golden.input}
        </span>
        <span className="font-mono text-[10px] text-muted flex-shrink-0">
          {passedCount}/{totalMetrics}
        </span>
        <span className="font-mono text-[10px] text-muted">
          {expanded ? "[-]" : "[+]"}
        </span>
      </button>
      {expanded && (
        <div className="px-3 pb-3">
          <div className="flex justify-start mb-2">
            <button
              onClick={copyGolden}
              className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-muted hover:text-text transition"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3" /> Copied
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" /> Copy
                </>
              )}
            </button>
          </div>
          <div className="space-y-3">
            {fieldBlock("Question", golden.input)}
            {golden.expected_output && fieldBlock("Expected Output", golden.expected_output)}
            {fieldBlock("Answer", golden.actual_output)}
          </div>
          <div className="space-y-2 mt-3">
            {golden.metrics.map((m: MetricResult, mi: number) => (
              <div key={mi} className="border border-line bg-panel px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
                    {METRIC_LABELS[m.name] || m.name}
                  </span>
                  <span className={`font-mono text-[11px] ${scoreColor(m.passed)}`}>
                    {m.score.toFixed(2)} {m.passed ? "✓" : "×"}
                  </span>
                </div>
                {m.reason && (
                  <p className="font-mono text-[10px] text-muted mt-1 leading-relaxed">
                    {m.reason}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function EvalPanel() {
  const { generation, evaluation, embedding, envGenerationApiKey, envEvalApiKey, envEmbedApiKey, sourcesCount } = useConfigStore();
  const effectiveGeneration = useMemo(
    () => ({ ...generation, apiKey: generation.apiKey || envGenerationApiKey }),
    [generation, envGenerationApiKey]
  );
  const effectiveEvaluation = useMemo(
    () => ({ ...evaluation, apiKey: evaluation.apiKey || envEvalApiKey }),
    [evaluation, envEvalApiKey]
  );
  const effectiveEmbedding = useMemo(
    () => ({ ...embedding, apiKey: embedding.apiKey || envEmbedApiKey }),
    [embedding, envEmbedApiKey]
  );

  const [summary, setSummary] = useState<EvalSummary | null>(null);
  const [running, setRunning] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [loadingResults, setLoadingResults] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState<"info" | "warn" | "error">("info");
  const [progressCount, setProgressCount] = useState(0);
  const [genStage, setGenStage] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [goldensExist, setGoldensExist] = useState(false);

  const refreshResults = useCallback(async () => {
    setLoadingResults(true);
    try {
      const s = await fetchEvalResults();
      setSummary(s);
    } catch {
      setSummary(null);
    } finally {
      setLoadingResults(false);
    }
  }, []);

  useEffect(() => { refreshResults(); }, [refreshResults]);

  useEffect(() => {
    fetchGoldensExist().then(setGoldensExist);
  }, []);

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => setMessage(""), 10000);
    return () => clearTimeout(timer);
  }, [message]);

  useEffect(() => {
    if (!generating) return;
    const interval = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(interval);
  }, [generating]);

  const handleRun = async () => {
    setRunning(true);
    setMessage("");
    setSummary(null);
    setProgressCount(0);
    try {
      const generator = streamEvalRun(effectiveGeneration, effectiveEvaluation, effectiveEmbedding);
      let result = await generator.next();
      while (!result.done) {
        if (result.value.type === "progress") {
          setProgressCount((c) => c + 1);
        }
        result = await generator.next();
      }
      if (result.value) {
        setSummary(result.value);
        setMessage(`Eval complete: ${result.value.passed}/${result.value.total} goldens passed.`);
        setMessageType("info");
      }
    } catch (e: any) {
      setMessage(e.message || "Eval run failed");
      setMessageType("error");
    } finally {
      setRunning(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setMessage("");
    setGenStage("Generating…");
    setElapsed(0);
    try {
      const generator = streamGenerateGoldens(effectiveEvaluation, effectiveEmbedding);
      let result = await generator.next();
      while (!result.done) {
        if (result.value.type === "progress") {
          setGenStage(result.value.value?.message || "Working…");
        }
        result = await generator.next();
      }
      if (result.value) {
        setMessage(`Generated ${result.value.count} goldens. You can now run evals.`);
        setMessageType("info");
        setGoldensExist(true);
      }
    } catch (e: any) {
      setMessage(e.message || "Golden generation failed");
      setMessageType("error");
    } finally {
      setGenerating(false);
      setGenStage("");
    }
  };

  const downloadResults = () => {
    if (!summary) return;
    const blob = new Blob([JSON.stringify(summary, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const ts = summary.run_at
      ? new Date(summary.run_at).toISOString().replace(/[:.]/g, "-")
      : Date.now();
    a.download = `eval-results-${ts}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const statusClass =
    messageType === "error"
      ? "text-text"
      : messageType === "warn"
      ? "text-muted"
      : "text-accent";

  return (
    <div className="space-y-6">
      {/* Step I: Ingest (text only — points to the Ingestion section above) */}
      <section>
        <p className={labelClass + " flex items-center gap-2"}>
          <span className="inline-flex items-center gap-2">
            {sourcesCount > 0 && <Check className="w-3.5 h-3.5 text-success" />}
            <span className="text-text">I.</span>
          </span>
          Add/Ingest Documents
        </p>
      </section>

      {/* Step II: Generate Goldens */}
      <section className="space-y-3">
        <div className="flex items-center gap-3">
          {goldensExist && <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />}
          <span className="font-mono text-[11px] uppercase tracking-widest text-text">II.</span>
          <button
            onClick={handleGenerate}
            disabled={generating || running}
            className={btnPrimary}
          >
            {generating ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                {genStage || "Generating…"}
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                Generate Goldens
              </>
            )}
          </button>
        </div>
        {generating && (
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Generating goldens… {elapsed}s
          </p>
        )}
      </section>

      {/* Step III: Run Evals */}
      <section className="space-y-3">
        <div className="flex items-center gap-3">
          {summary && <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />}
          <span className="font-mono text-[11px] uppercase tracking-widest text-text">III.</span>
          <button onClick={handleRun} disabled={running || generating} className={btnPrimary}>
            {running ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Running ({progressCount} done)
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                Run Evals
              </>
            )}
          </button>
        </div>
        {running && (
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Streaming results as goldens complete…
          </p>
        )}
      </section>

      {/* Summary */}
      {summary && (
        <section className="space-y-3">
          <div className="flex items-center justify-between border border-line bg-panel px-3 py-3">
            <div>
              <p className={labelClass}>Pass Rate</p>
              <p className={`font-mono text-lg ${scoreColor(summary.passed === summary.total)}`}>
                {summary.passed}/{summary.total}
              </p>
            </div>
            <button
              onClick={refreshResults}
              disabled={loadingResults}
              className="text-muted hover:text-text transition p-1"
              aria-label="Refresh results"
            >
              <RefreshCw className={`w-3 h-3 ${loadingResults ? "animate-spin" : ""}`} />
            </button>
          </div>

          {/* Metric averages */}
          <div className="space-y-2">
            {summary.metric_averages.map((m, i) => (
              <div key={i} className="flex items-center justify-between border border-line bg-panel px-3 py-2">
                <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
                  {METRIC_LABELS[m.name] || m.name}
                </span>
                <div className="flex items-center gap-3">
                  <span className={`font-mono text-[11px] ${scoreColor(m.pass_rate >= 0.5)}`}>
                    {(m.pass_rate * 100).toFixed(0)}%
                  </span>
                  <span className="font-mono text-[11px] text-text">
                    {m.avg_score.toFixed(2)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Per-golden detail */}
      {summary && summary.goldens.length > 0 && (
        <section className="space-y-2">
          <p className={labelClass}>Per-Golden Results</p>
          <div className="border border-line bg-panel overflow-hidden">
            {summary.goldens.map((g, i) => (
              <GoldenRow key={i} golden={g} index={i} />
            ))}
          </div>
        </section>
      )}

      {/* Download complete results */}
      {!running && summary && (
        <button onClick={downloadResults} className={btnOutline}>
          <Download className="w-3.5 h-3.5" />
          Download Results
        </button>
      )}

      {/* Empty state */}
      {!summary && !running && (
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
          No eval results yet. Run evals or click refresh to load from disk.
        </p>
      )}

      {/* Refresh from disk */}
      {!running && (
        <button onClick={refreshResults} disabled={loadingResults} className={btnOutline}>
          {loadingResults && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          Load Latest Results
        </button>
      )}

      {/* Status message */}
      {message && (
        <p className={`font-mono text-[11px] uppercase tracking-widest ${statusClass}`}>
          {messageType === "error" && <span className="mr-1">×</span>}
          {message}
        </p>
      )}
    </div>
  );
}