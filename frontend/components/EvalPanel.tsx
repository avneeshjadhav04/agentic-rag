"use client";

import { useConfigStore } from "@/store/configStore";
import { fetchEvalResults, fetchEvalResultByName, fetchGoldensExist, listEvalRuns, listGoldens, streamEvalRun, addGolden, importGoldens, clearGoldens, deleteGolden, clearEvalRuns, deleteEvalRun } from "@/lib/api";
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Loader2, RefreshCw, Play, Plus, Minus, Copy, Check, Download, Upload, X } from "lucide-react";
import { EvalSummary, GoldenResult, MetricResult, StoredEvalRun, StoredGolden, EvalProviders } from "@/types";

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
  const [loadingResults, setLoadingResults] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState<"info" | "warn" | "error">("info");
  const [progressCount, setProgressCount] = useState(0);
  const [goldensExist, setGoldensExist] = useState(false);
  const [storedGoldens, setStoredGoldens] = useState<StoredGolden[]>([]);
  const [storedRuns, setStoredRuns] = useState<StoredEvalRun[]>([]);
  const [goldensExpanded, setGoldensExpanded] = useState(false);
  const [runsExpanded, setRunsExpanded] = useState(false);
  const [loadingStoredGoldens, setLoadingStoredGoldens] = useState(false);
  const [loadingStoredRuns, setLoadingStoredRuns] = useState(false);
  const [copiedGoldenIdx, setCopiedGoldenIdx] = useState<number | null>(null);
  const [loadingRunFile, setLoadingRunFile] = useState<string | null>(null);
  const [loadedRunFilename, setLoadedRunFilename] = useState<string | null>(null);
  const [clearingGoldens, setClearingGoldens] = useState(false);
  const [deletingGolden, setDeletingGolden] = useState<number | null>(null);
  const [clearingRuns, setClearingRuns] = useState(false);
  const [deletingRun, setDeletingRun] = useState<string | null>(null);
  const [downloadingRun, setDownloadingRun] = useState<string | null>(null);
  const [goldenProviders, setGoldenProviders] = useState<EvalProviders>({});
  const [newGoldenInput, setNewGoldenInput] = useState("");
  const [newGoldenExpected, setNewGoldenExpected] = useState("");
  const [addingGolden, setAddingGolden] = useState(false);
  const [uploadingGoldens, setUploadingGoldens] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const refreshStoredGoldens = useCallback(async () => {
    setLoadingStoredGoldens(true);
    try {
      const res = await listGoldens();
      setStoredGoldens(res.goldens);
      setGoldenProviders(res.providers);
    } catch {
      setStoredGoldens([]);
      setGoldenProviders({});
    } finally {
      setLoadingStoredGoldens(false);
    }
  }, []);

  const refreshStoredRuns = useCallback(async () => {
    setLoadingStoredRuns(true);
    try {
      setStoredRuns(await listEvalRuns());
    } catch {
      setStoredRuns([]);
    } finally {
      setLoadingStoredRuns(false);
    }
  }, []);

  useEffect(() => {
    refreshStoredGoldens();
    refreshStoredRuns();
  }, [refreshStoredGoldens, refreshStoredRuns]);

  const loadRunFile = useCallback(async (filename: string) => {
    setLoadingRunFile(filename);
    try {
      const s = await fetchEvalResultByName(filename);
      if (s) {
        setSummary(s);
        setLoadedRunFilename(filename);
        setMessage(`Loaded run ${filename}.`);
        setMessageType("info");
      } else {
        setMessage(`Failed to load run ${filename}.`);
        setMessageType("error");
      }
    } finally {
      setLoadingRunFile(null);
    }
  }, []);

  const copyGolden = useCallback((g: StoredGolden) => {
    navigator.clipboard.writeText(JSON.stringify(g, null, 2));
    setCopiedGoldenIdx(g.index);
    setTimeout(() => setCopiedGoldenIdx(null), 2000);
  }, []);

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => setMessage(""), 10000);
    return () => clearTimeout(timer);
  }, [message]);

  const handleRun = async () => {
    setRunning(true);
    setMessage("");
    setSummary(null);
    setLoadedRunFilename(null);
    setProgressCount(0);
    let gotSummary = false;
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
        setLoadedRunFilename(null);
        setMessage(`Eval complete: ${result.value.passed}/${result.value.total} goldens passed.`);
        setMessageType("info");
        gotSummary = true;
      }
    } catch (e: any) {
      setMessage(e.message || "Eval run failed");
      setMessageType("error");
    } finally {
      if (!gotSummary) {
        // The SSE connection may have died before the backend finished.
        // Poll for the results — the backend thread is still running and
        // will write the file when it completes. Try every 5s for up to 30 min.
        setMessage("Connection lost — waiting for backend to finish…");
        setMessageType("warn");
        for (let attempt = 0; attempt < 360; attempt++) {
          await new Promise((r) => setTimeout(r, 5000));
          const s = await fetchEvalResults();
          if (s) {
            setSummary(s);
            setLoadedRunFilename(null);
            setMessage(`Eval complete: ${s.passed}/${s.total} goldens passed.`);
            setMessageType("info");
            break;
          }
        }
      }
      refreshStoredRuns();
      setRunning(false);
    }
  };

  const handleAddGolden = async () => {
    const input = newGoldenInput.trim();
    const expected = newGoldenExpected.trim();
    if (!input || !expected) return;
    setAddingGolden(true);
    try {
      await addGolden(input, expected);
      setNewGoldenInput("");
      setNewGoldenExpected("");
      setGoldensExist(true);
      refreshStoredGoldens();
      setMessage("Golden added.");
      setMessageType("info");
    } catch (e: any) {
      setMessage(e.message || "Failed to add golden");
      setMessageType("error");
    } finally {
      setAddingGolden(false);
    }
  };

  const handleUploadGoldens = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    setUploadingGoldens(true);
    try {
      const result = await importGoldens(files);
      setGoldensExist(true);
      refreshStoredGoldens();
      const skipMsg = result.skipped > 0 ? `, skipped ${result.skipped} invalid` : "";
      setMessage(`Imported ${result.imported} golden${result.imported === 1 ? "" : "s"}${skipMsg}.`);
      setMessageType("info");
    } catch (err: any) {
      setMessage(err.message || "Failed to upload goldens");
      setMessageType("error");
    } finally {
      setUploadingGoldens(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
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

  const downloadGolden = (g: StoredGolden) => {
    const payload = { providers: goldenProviders, golden: { index: g.index, input: g.input, expected_output: g.expected_output } };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `golden-${g.index}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const downloadAllGoldens = () => {
    const payload = { providers: goldenProviders, goldens: storedGoldens };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `goldens.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleClearGoldens = async () => {
    setClearingGoldens(true);
    setMessage("");
    try {
      const ok = await clearGoldens();
      if (ok) {
        setMessage("Cleared all goldens.");
        setMessageType("info");
        setGoldensExist(false);
        refreshStoredGoldens();
      } else {
        setMessage("Failed to clear goldens.");
        setMessageType("error");
      }
    } finally {
      setClearingGoldens(false);
    }
  };

  const handleDeleteGolden = async (index: number) => {
    setDeletingGolden(index);
    setMessage("");
    try {
      const ok = await deleteGolden(index);
      if (ok) {
        setMessage(`Removed golden #${index}.`);
        setMessageType("info");
        refreshStoredGoldens();
        fetchGoldensExist().then(setGoldensExist);
      } else {
        setMessage(`Failed to remove golden #${index}.`);
        setMessageType("error");
      }
    } finally {
      setDeletingGolden(null);
    }
  };

  const handleClearRuns = async () => {
    setClearingRuns(true);
    setMessage("");
    try {
      const ok = await clearEvalRuns();
      if (ok) {
        setMessage("Cleared all eval runs.");
        setMessageType("info");
        setSummary(null);
        setLoadedRunFilename(null);
        refreshStoredRuns();
      } else {
        setMessage("Failed to clear eval runs.");
        setMessageType("error");
      }
    } finally {
      setClearingRuns(false);
    }
  };

  const handleDeleteRun = async (filename: string) => {
    setDeletingRun(filename);
    setMessage("");
    try {
      const ok = await deleteEvalRun(filename);
      if (ok) {
        setMessage(`Removed ${filename}.`);
        setMessageType("info");
        if (loadedRunFilename === filename) {
          setSummary(null);
          setLoadedRunFilename(null);
        }
        refreshStoredRuns();
      } else {
        setMessage(`Failed to remove ${filename}.`);
        setMessageType("error");
      }
    } finally {
      setDeletingRun(null);
    }
  };

  const handleDownloadRun = async (filename: string) => {
    setDownloadingRun(filename);
    setMessage("");
    try {
      const s = await fetchEvalResultByName(filename);
      if (s) {
        let ts: string;
        if (s.run_at) {
          ts = new Date(s.run_at).toISOString().replace(/[:.]/g, "-");
        } else {
          const m = filename.match(/(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z/);
          ts = m ? `${m[1]}-${m[2]}-${m[3]}T${m[4]}-${m[5]}-${m[6]}Z` : String(Date.now());
        }
        const blob = new Blob([JSON.stringify(s, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `eval-results-${ts}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } else {
        setMessage(`Failed to download ${filename}.`);
        setMessageType("error");
      }
    } finally {
      setDownloadingRun(null);
    }
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

      {/* Step II: Run Evals */}
      <section className="space-y-3">
        <div className="flex items-center gap-3">
          {summary && <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />}
          <span className="font-mono text-[11px] uppercase tracking-widest text-text">II.</span>
          <button onClick={handleRun} disabled={running} className={btnPrimary}>
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
          No eval results yet. Run evals to get started.
        </p>
      )}

      {/* Stored Goldens */}
      <div className="border border-line bg-panel overflow-hidden">
        <button
          onClick={() => setGoldensExpanded(!goldensExpanded)}
          className="flex items-center justify-between w-full px-3 py-2.5 font-mono text-[11px] uppercase tracking-widest text-muted hover:text-text transition"
        >
          <span>
            <span className="text-text">Stored Goldens</span>
            <span className="ml-2">/ {storedGoldens.length}</span>
          </span>
          <span className="flex items-center gap-2">
            <span
              role="button"
              onClick={(e) => { e.stopPropagation(); refreshStoredGoldens(); }}
              className="p-1 hover:text-text"
            >
              <RefreshCw className={`w-3 h-3 ${loadingStoredGoldens ? "animate-spin" : ""}`} />
            </span>
            {goldensExpanded ? <Minus className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
          </span>
        </button>
        {goldensExpanded && (
          <div className="px-3 pb-3 space-y-2">
            <div className="space-y-1.5">
              <textarea
                value={newGoldenInput}
                onChange={(e) => setNewGoldenInput(e.target.value)}
                disabled={addingGolden}
                placeholder="Question"
                rows={2}
                className="w-full bg-panel border border-line rounded-none px-3 py-2 text-sm text-text placeholder-muted transition disabled:opacity-40 resize-none"
              />
              <textarea
                value={newGoldenExpected}
                onChange={(e) => setNewGoldenExpected(e.target.value)}
                disabled={addingGolden}
                placeholder="Expected answer"
                rows={3}
                className="w-full bg-panel border border-line rounded-none px-3 py-2 text-sm text-text placeholder-muted transition disabled:opacity-40 resize-none"
              />
              <button
                onClick={handleAddGolden}
                disabled={addingGolden || !newGoldenInput.trim() || !newGoldenExpected.trim()}
                className={btnPrimary + " w-fit"}
              >
                {addingGolden ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Adding…
                  </>
                ) : (
                  <>
                    <Plus className="w-3.5 h-3.5" />
                    Add Golden
                  </>
                )}
              </button>
              <div className="flex items-center gap-2 pt-1">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".json"
                  multiple
                  onChange={handleUploadGoldens}
                  disabled={uploadingGoldens}
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadingGoldens || addingGolden}
                  className="flex items-center gap-2 px-4 py-2 rounded-none border border-line text-muted font-mono text-[11px] uppercase tracking-widest hover:border-accent hover:text-text transition disabled:opacity-40"
                >
                  {uploadingGoldens ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Uploading…
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" />
                      Upload Goldens
                    </>
                  )}
                </button>
              </div>
            </div>
            <div className="max-h-40 overflow-y-auto space-y-1">
            {storedGoldens.length === 0 ? (
              <p className="font-mono text-[10px] uppercase tracking-widest text-muted">No goldens stored yet.</p>
            ) : (
              storedGoldens.map((g, i) => (
                <div key={i} className="flex items-center gap-2 group">
                  <p className="font-mono text-[11px] text-text truncate flex-1" title={g.input}>
                    {g.input}
                  </p>
                  <button
                    onClick={() => copyGolden(g)}
                    className="text-muted hover:text-text transition flex-shrink-0"
                    aria-label="Copy golden"
                  >
                    {copiedGoldenIdx === g.index ? (
                      <Check className="w-3 h-3 text-success" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                  <button
                    onClick={() => downloadGolden(g)}
                    className="text-muted hover:text-text transition flex-shrink-0"
                    aria-label="Download golden"
                  >
                    <Download className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => handleDeleteGolden(g.index)}
                    disabled={deletingGolden !== null || clearingGoldens}
                    className="text-muted hover:text-text transition flex-shrink-0 disabled:opacity-40"
                    aria-label="Remove golden"
                  >
                    {deletingGolden === g.index ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <X className="w-3 h-3" />
                    )}
                  </button>
                </div>
              ))
            )}
            {storedGoldens.length > 0 && (
              <div className="pt-1 flex items-center gap-4">
                <button
                  onClick={handleClearGoldens}
                  disabled={clearingGoldens || deletingGolden !== null}
                  className="font-mono text-[10px] uppercase tracking-widest text-muted hover:text-text transition disabled:opacity-40"
                >
                  {clearingGoldens ? <Loader2 className="w-3 h-3 animate-spin" /> : "Clear All"}
                </button>
                <button
                  onClick={downloadAllGoldens}
                  className="font-mono text-[10px] uppercase tracking-widest text-muted hover:text-text transition"
                >
                  Download All
                </button>
              </div>
            )}
            </div>
          </div>
        )}
      </div>

      {/* Stored Evals */}
      <div className="border border-line bg-panel overflow-hidden">
        <button
          onClick={() => setRunsExpanded(!runsExpanded)}
          className="flex items-center justify-between w-full px-3 py-2.5 font-mono text-[11px] uppercase tracking-widest text-muted hover:text-text transition"
        >
          <span>
            <span className="text-text">Stored Evals</span>
            <span className="ml-2">/ {storedRuns.length}</span>
          </span>
          <span className="flex items-center gap-2">
            <span
              role="button"
              onClick={(e) => { e.stopPropagation(); refreshStoredRuns(); }}
              className="p-1 hover:text-text"
            >
              <RefreshCw className={`w-3 h-3 ${loadingStoredRuns ? "animate-spin" : ""}`} />
            </span>
            {runsExpanded ? <Minus className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
          </span>
        </button>
        {runsExpanded && (
          <div className="px-3 pb-3 max-h-40 overflow-y-auto space-y-1">
            {storedRuns.length === 0 ? (
              <p className="font-mono text-[10px] uppercase tracking-widest text-muted">No eval runs stored yet.</p>
            ) : (
              storedRuns.map((r, i) => (
                <div key={i} className="flex items-center justify-between gap-2 px-1 py-0.5 hover:bg-line transition">
                  <button
                    onClick={() => loadRunFile(r.filename)}
                    disabled={loadingRunFile !== null || deletingRun !== null || clearingRuns || downloadingRun !== null}
                    className="flex items-center gap-2 flex-1 min-w-0 text-left disabled:opacity-40"
                  >
                    <span className="font-mono text-[11px] text-text truncate flex-1" title={r.filename}>
                      {r.label}
                    </span>
                    {r.passed !== null && r.total !== null && (
                      <span className={`font-mono text-[10px] ${r.passed === r.total ? "text-success" : "text-muted"}`}>
                        {r.passed}/{r.total}
                      </span>
                    )}
                    {loadingRunFile === r.filename ? (
                      <Loader2 className="w-3 h-3 animate-spin flex-shrink-0" />
                    ) : (
                      <span className="font-mono text-[10px] text-muted flex-shrink-0">[load]</span>
                    )}
                  </button>
                  <button
                    onClick={() => handleDownloadRun(r.filename)}
                    disabled={downloadingRun !== null || deletingRun !== null || clearingRuns || loadingRunFile !== null}
                    className="text-muted hover:text-text transition flex-shrink-0 disabled:opacity-40"
                    aria-label="Download eval run"
                  >
                    {downloadingRun === r.filename ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <Download className="w-3 h-3" />
                    )}
                  </button>
                  <button
                    onClick={() => handleDeleteRun(r.filename)}
                    disabled={deletingRun !== null || clearingRuns || loadingRunFile !== null || downloadingRun !== null}
                    className="text-muted hover:text-text transition flex-shrink-0 disabled:opacity-40"
                    aria-label="Remove eval run"
                  >
                    {deletingRun === r.filename ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <X className="w-3 h-3" />
                    )}
                  </button>
                </div>
              ))
            )}
            {storedRuns.length > 0 && (
              <div className="pt-1">
                <button
                  onClick={handleClearRuns}
                  disabled={clearingRuns || deletingRun !== null || downloadingRun !== null}
                  className="font-mono text-[10px] uppercase tracking-widest text-muted hover:text-text transition disabled:opacity-40"
                >
                  {clearingRuns ? <Loader2 className="w-3 h-3 animate-spin" /> : "Clear All"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

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