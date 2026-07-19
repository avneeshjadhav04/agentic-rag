"use client";

import { useConfigStore } from "@/store/configStore";
import { clearStore, ingestFiles, ingestUrls } from "@/lib/api";
import { useState } from "react";
import { FileUp, Link2, Trash2, Loader2 } from "lucide-react";

export default function IngestionPanel() {
  const { embedding, chunkSize, chunkOverlap, setChunkSize, setChunkOverlap } = useConfigStore();
  const [urls, setUrls] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const handleFiles = async () => {
    if (!files || files.length === 0) return;
    setLoading(true);
    setMessage("");
    try {
      const res = await ingestFiles(files, embedding, chunkSize, chunkOverlap);
      setMessage(`Ingested ${res.ingested} chunks from ${files.length} files.`);
      setFiles(null);
    } catch (e: any) {
      setMessage(e.message || "File ingestion failed");
    } finally {
      setLoading(false);
    }
  };

  const handleUrls = async () => {
    if (!urls.trim()) return;
    setLoading(true);
    setMessage("");
    try {
      const res = await ingestUrls(urls, embedding, chunkSize, chunkOverlap);
      setMessage(`Ingested ${res.ingested} chunks from ${res.url_count} URLs.`);
      setUrls("");
    } catch (e: any) {
      setMessage(e.message || "URL ingestion failed");
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    setLoading(true);
    setMessage("");
    try {
      await clearStore(embedding);
      setMessage("Vector store cleared.");
    } catch (e: any) {
      setMessage(e.message || "Failed to clear store");
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    "w-full bg-panel border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-muted focus:border-primary transition";
  const btnClass =
    "flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-dark transition disabled:opacity-50";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-primary">
        <FileUp className="w-5 h-5" />
        <h2 className="text-lg font-semibold">Ingestion</h2>
      </div>

      {/* Chunk settings */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-xs text-muted">Chunk Size</label>
          <input
            type="number"
            value={chunkSize}
            onChange={(e) => setChunkSize(parseInt(e.target.value) || 1000)}
            className={inputClass}
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted">Overlap</label>
          <input
            type="number"
            value={chunkOverlap}
            onChange={(e) => setChunkOverlap(parseInt(e.target.value) || 200)}
            className={inputClass}
          />
        </div>
      </div>

      {/* File upload */}
      <section className="space-y-3">
        <p className="text-sm font-medium text-text">Upload Files</p>
        <input
          type="file"
          multiple
          onChange={(e) => setFiles(e.target.files)}
          className="block w-full text-sm text-muted file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-panel file:text-text hover:file:border-primary"
        />
        <button onClick={handleFiles} disabled={loading || !files} className={btnClass}>
          {loading && <Loader2 className="w-4 h-4 animate-spin" />}
          Ingest Files
        </button>
      </section>

      {/* URL ingestion */}
      <section className="space-y-3">
        <div className="flex items-center gap-2 text-text">
          <Link2 className="w-4 h-4" />
          <p className="text-sm font-medium">URLs (one per line or comma-separated)</p>
        </div>
        <textarea
          value={urls}
          onChange={(e) => setUrls(e.target.value)}
          rows={4}
          placeholder="https://example.com/article, https://..."
          className={inputClass}
        />
        <button onClick={handleUrls} disabled={loading || !urls.trim()} className={btnClass}>
          {loading && <Loader2 className="w-4 h-4 animate-spin" />}
          Ingest URLs
        </button>
      </section>

      {/* Clear store */}
      <button
        onClick={handleClear}
        disabled={loading}
        className="flex items-center justify-center gap-2 w-full px-4 py-2 rounded-lg border border-red-500/50 text-red-400 text-sm font-medium hover:bg-red-500/10 transition"
      >
        <Trash2 className="w-4 h-4" /> Clear Vector Store
      </button>

      {message && (
        <p className="text-xs text-primary">{message}</p>
      )}
    </div>
  );
}
