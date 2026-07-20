"use client";

import { useConfigStore } from "@/store/configStore";
import { clearStore, deleteSource, ingestFiles, ingestUrls, listSources } from "@/lib/api";
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Loader2, RefreshCw, Plus, Minus, X } from "lucide-react";

const labelClass = "font-mono text-[10px] uppercase tracking-widest text-muted";
const inputClass =
  "w-full bg-panel border border-line rounded-none px-3 py-2 text-sm text-text placeholder-muted transition";
const btnPrimary =
  "flex items-center justify-center gap-2 px-4 py-2 rounded-none bg-accent text-background font-mono text-[11px] uppercase tracking-widest hover:bg-accent/80 transition disabled:opacity-40";
const btnOutline =
  "flex items-center justify-center gap-2 w-full px-4 py-2 rounded-none border border-line text-muted font-mono text-[11px] uppercase tracking-widest hover:border-accent hover:text-text transition disabled:opacity-40";

export default function IngestionPanel() {
  const { embedding, envEmbedApiKey, chunkSize, chunkOverlap } = useConfigStore();
  const effectiveEmbedding = useMemo(
    () => ({ ...embedding, apiKey: embedding.apiKey || envEmbedApiKey }),
    [embedding, envEmbedApiKey]
  );
  const [urls, setUrls] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [filesLoading, setFilesLoading] = useState(false);
  const [urlsLoading, setUrlsLoading] = useState(false);
  const [clearLoading, setClearLoading] = useState(false);
  const loading = filesLoading || urlsLoading || clearLoading;
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState<"info" | "warn" | "error">("info");
  const [sources, setSources] = useState<string[]>([]);
  const [loadingSources, setLoadingSources] = useState(false);
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const [deletingSource, setDeletingSource] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refreshSources = useCallback(async () => {
    setLoadingSources(true);
    try {
      const s = await listSources(effectiveEmbedding);
      setSources(s);
    } catch {
      setSources([]);
    } finally {
      setLoadingSources(false);
    }
  }, [effectiveEmbedding]);

  useEffect(() => { refreshSources(); }, [refreshSources]);

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => setMessage(""), 10000);
    return () => clearTimeout(timer);
  }, [message]);

  const handleFiles = async () => {
    if (!files || files.length === 0) return;
    setFilesLoading(true);
    setMessage("");
    try {
      const res = await ingestFiles(files, effectiveEmbedding, chunkSize, chunkOverlap);
      const failed = (res.files || []).filter((f: any) => f.status === "error");
      const warned = (res.files || []).filter((f: any) => f.status === "warning");
      const msgs: string[] = [];
      if (failed.length) msgs.push(`${failed.length} file(s) failed`);
      if (warned.length) msgs.push(`${warned.length} file(s) had no extractable text (scanned?)`);
      const hasIssues = failed.length || warned.length || res.ingested === 0;
      const msg = hasIssues
        ? `Ingested ${res.ingested} chunks (${msgs.join("; ") || "0 chunks"})`
        : `Ingested ${res.ingested} chunks from ${files.length} files.`;
      setMessage(msg);
      setMessageType(failed.length ? "error" : warned.length || res.ingested === 0 ? "warn" : "info");
      setFiles(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      refreshSources();
    } catch (e: any) {
      setMessage(e.message || "File ingestion failed");
      setMessageType("error");
    } finally {
      setFilesLoading(false);
    }
  };

  const handleUrls = async () => {
    if (!urls.trim()) return;
    setUrlsLoading(true);
    setMessage("");
    try {
      const res = await ingestUrls(urls, effectiveEmbedding, chunkSize, chunkOverlap);
      setMessage(`Ingested ${res.ingested} chunks from ${res.url_count} URLs.`);
      setMessageType(res.ingested === 0 ? "warn" : "info");
      setUrls("");
      refreshSources();
    } catch (e: any) {
      setMessage(e.message || "URL ingestion failed");
      setMessageType("error");
    } finally {
      setUrlsLoading(false);
    }
  };

  const handleClear = async () => {
    setClearLoading(true);
    setMessage("");
    try {
      await clearStore(effectiveEmbedding);
      setMessage("Vector store cleared.");
      setMessageType("info");
      refreshSources();
    } catch (e: any) {
      setMessage(e.message || "Failed to clear store");
      setMessageType("error");
    } finally {
      setClearLoading(false);
    }
  };

  const handleDeleteSource = async (source: string) => {
    setDeletingSource(source);
    setMessage("");
    try {
      await deleteSource(source, effectiveEmbedding);
      setMessage(`Removed ${source}.`);
      setMessageType("info");
      refreshSources();
    } catch (e: any) {
      setMessage(e.message || "Failed to delete source");
      setMessageType("error");
    } finally {
      setDeletingSource(null);
    }
  };

  const statusClass =
    messageType === "error"
      ? "text-text"
      : messageType === "warn"
      ? "text-muted"
      : "text-accent";

  return (
    <div className="space-y-8">
      {/* File upload */}
      <section className="space-y-3">
        <p className={labelClass}>Upload Files</p>
        <input
          type="file"
          multiple
          ref={fileInputRef}
          onChange={(e) => setFiles(e.target.files)}
          className="block w-full text-xs text-muted file:mr-4 file:py-2 file:px-3 file:rounded-none file:border file:border-line file:bg-panel file:text-text file:font-mono file:text-[10px] file:uppercase file:tracking-widest hover:file:border-accent transition"
        />
        <button onClick={handleFiles} disabled={filesLoading || !files} className={btnPrimary}>
          {filesLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          Ingest Files
        </button>
      </section>

      {/* URL ingestion */}
      <section className="space-y-3">
        <p className={labelClass}>URLs</p>
        <textarea
          value={urls}
          onChange={(e) => setUrls(e.target.value)}
          rows={2}
          placeholder="https://example.com/article, https://..."
          className={inputClass}
        />
        <button onClick={handleUrls} disabled={urlsLoading || !urls.trim()} className={btnPrimary}>
          {urlsLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          Ingest URLs
        </button>
      </section>

      {/* Stored Sources */}
      <div className="border border-line bg-panel overflow-hidden">
        <button
          onClick={() => setSourcesExpanded(!sourcesExpanded)}
          className="flex items-center justify-between w-full px-3 py-2.5 font-mono text-[11px] uppercase tracking-widest text-muted hover:text-text transition"
        >
          <span>
            <span className="text-text">Stored Sources</span>
            <span className="ml-2">/ {sources.length}</span>
          </span>
          <span className="flex items-center gap-2">
            <span
              role="button"
              onClick={(e) => { e.stopPropagation(); refreshSources(); }}
              className="p-1 hover:text-text"
            >
              <RefreshCw className={`w-3 h-3 ${loadingSources ? "animate-spin" : ""}`} />
            </span>
            {sourcesExpanded ? <Minus className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
          </span>
        </button>
        {sourcesExpanded && (
          <div className="px-3 pb-3 max-h-40 overflow-y-auto space-y-1">
            {sources.length === 0 ? (
              <p className="font-mono text-[10px] uppercase tracking-widest text-muted">No sources stored yet.</p>
            ) : (
              sources.map((s, i) => (
                <div key={i} className="flex items-center gap-2 group">
                  <p className="font-mono text-[11px] text-text truncate flex-1" title={s}>{s}</p>
                  <button
                    onClick={() => handleDeleteSource(s)}
                    disabled={deletingSource !== null}
                    className="text-muted hover:text-text transition flex-shrink-0 disabled:opacity-40"
                    aria-label={`Remove ${s}`}
                  >
                    {deletingSource === s ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <X className="w-3 h-3" />
                    )}
                  </button>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Clear store */}
      <button onClick={handleClear} disabled={loading} className={btnOutline}>
        Clear Vector Store
      </button>

      {message && (
        <p className={`font-mono text-[11px] uppercase tracking-widest ${statusClass}`}>
          {messageType === "error" && <span className="mr-1">×</span>}
          {message}
        </p>
      )}
    </div>
  );
}