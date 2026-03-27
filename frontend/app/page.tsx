"use client";

import { useMemo, useState } from "react";

type SourceItem = {
  source_index: number;
  source: string;
  summary: string;
  approved: boolean | null;
};

type ReportItem = {
  source: string;
  summary: string;
};

const API_BASE = "http://localhost:8000";

function Spinner() {
  return (
    <div className="flex items-center gap-3 text-sm text-zinc-300">
      <div className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-600 border-t-zinc-200" />
      <span>Agent is researching...</span>
    </div>
  );
}

export default function Home() {
  const [topic, setTopic] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [items, setItems] = useState<SourceItem[]>([]);
  const [reportItems, setReportItems] = useState<ReportItem[] | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  const allReviewed = useMemo(() => {
    return items.length > 0 && items.every((it) => it.approved !== null);
  }, [items]);

  async function startResearch() {
    setError(null);
    setReportItems(null);
    setItems([]);
    setJobId(null);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Request failed (${res.status})`);
      }
      const data: { job_id: string } = await res.json();
      setJobId(data.job_id);

      const srcRes = await fetch(`${API_BASE}/research/${data.job_id}/sources`);
      if (!srcRes.ok) {
        const text = await srcRes.text();
        throw new Error(text || `Request failed (${srcRes.status})`);
      }
      const srcData: { topic: string; items: SourceItem[] } = await srcRes.json();
      setItems(srcData.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function decide(sourceIndex: number, approved: boolean) {
    if (!jobId) return;
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/research/${jobId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_index: sourceIndex, approved }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Request failed (${res.status})`);
      }
      setItems((prev) =>
        prev.map((it) =>
          it.source_index === sourceIndex ? { ...it, approved } : it,
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    }
  }

  async function viewReport() {
    if (!jobId) return;
    setError(null);
    setReportLoading(true);
    try {
      const res = await fetch(`${API_BASE}/research/${jobId}/report`);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Request failed (${res.status})`);
      }
      const data: { topic: string; approved_items: ReportItem[] } = await res.json();
      setReportItems(data.approved_items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setReportLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto w-full max-w-5xl px-4 py-10">
        <header className="mb-8">
          <h1 className="text-xl font-semibold tracking-tight">Research Agent</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Submit a topic, review sources, then generate a final report.
          </p>
        </header>

        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4">
          <form
            className="flex flex-col gap-3 sm:flex-row sm:items-center"
            onSubmit={(e) => {
              e.preventDefault();
              if (loading) return;
              if (!topic.trim()) {
                setError("Please enter a topic.");
                return;
              }
              startResearch();
            }}
          >
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g., Latest advances in solid-state batteries"
              className="h-11 w-full flex-1 rounded-xl border border-zinc-800 bg-zinc-950 px-3 text-sm text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-zinc-600"
            />
            <button
              type="submit"
              disabled={loading}
              className="h-11 rounded-xl bg-zinc-100 px-4 text-sm font-medium text-zinc-950 hover:bg-white disabled:cursor-not-allowed disabled:opacity-70"
            >
              Research
            </button>
          </form>

          <div className="mt-4 flex items-center justify-between gap-3">
            {loading ? <Spinner /> : <div />}
            {jobId ? (
              <div className="text-xs text-zinc-500">
                Job ID: <span className="font-mono text-zinc-300">{jobId}</span>
              </div>
            ) : null}
          </div>

          {error ? (
            <div className="mt-4 rounded-xl border border-red-900/60 bg-red-950/40 p-3 text-sm text-red-200">
              {error}
            </div>
          ) : null}
        </div>

        {items.length > 0 ? (
          <section className="mt-8">
            <div className="mb-4 flex items-end justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold">Sources</h2>
                <p className="mt-1 text-sm text-zinc-400">
                  Approve or reject each source.
                </p>
              </div>
              {allReviewed ? (
                <div className="text-xs text-zinc-400">All sources reviewed</div>
              ) : (
                <div className="text-xs text-zinc-400">
                  Reviewed{" "}
                  <span className="text-zinc-200">
                    {items.filter((it) => it.approved !== null).length}/{items.length}
                  </span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 gap-4">
              {items.map((it) => (
                <div
                  key={it.source_index}
                  className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4"
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="text-xs text-zinc-500">
                        Source #{it.source_index}
                      </div>
                      <a
                        href={it.source}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-1 block break-all text-sm font-medium text-zinc-100 hover:underline"
                      >
                        {it.source}
                      </a>
                      <p className="mt-2 text-sm leading-6 text-zinc-300">
                        {it.summary}
                      </p>
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      <button
                        type="button"
                        onClick={() => decide(it.source_index, true)}
                        className={`h-9 rounded-xl px-3 text-sm font-medium ${
                          it.approved === true
                            ? "bg-emerald-400 text-zinc-950"
                            : "bg-zinc-100 text-zinc-950 hover:bg-white"
                        }`}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        onClick={() => decide(it.source_index, false)}
                        className={`h-9 rounded-xl px-3 text-sm font-medium ${
                          it.approved === false
                            ? "bg-rose-400 text-zinc-950"
                            : "bg-zinc-800 text-zinc-100 hover:bg-zinc-700"
                        }`}
                      >
                        Reject
                      </button>
                    </div>
                  </div>

                  <div className="mt-3 text-xs text-zinc-500">
                    Decision:{" "}
                    <span className="text-zinc-300">
                      {it.approved === null
                        ? "Not reviewed"
                        : it.approved
                          ? "Approved"
                          : "Rejected"}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {allReviewed ? (
              <div className="mt-6 flex items-center gap-3">
                <button
                  type="button"
                  onClick={viewReport}
                  disabled={reportLoading}
                  className="h-11 rounded-xl bg-zinc-100 px-4 text-sm font-medium text-zinc-950 hover:bg-white disabled:cursor-not-allowed disabled:opacity-70"
                >
                  View Report
                </button>
                {reportLoading ? (
                  <div className="text-sm text-zinc-400">Loading report...</div>
                ) : null}
              </div>
            ) : null}
          </section>
        ) : null}

        {reportItems ? (
          <section className="mt-10">
            <div className="mb-4">
              <h2 className="text-base font-semibold">Final Report</h2>
              <p className="mt-1 text-sm text-zinc-400">
                Approved sources and summaries.
              </p>
            </div>

            {reportItems.length === 0 ? (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-300">
                No approved sources.
              </div>
            ) : (
              <div className="space-y-4">
                {reportItems.map((it, idx) => (
                  <div
                    key={`${it.source}-${idx}`}
                    className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4"
                  >
                    <div className="text-xs text-zinc-500">Approved #{idx + 1}</div>
                    <a
                      href={it.source}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 block break-all text-sm font-medium text-zinc-100 hover:underline"
                    >
                      {it.source}
                    </a>
                    <p className="mt-2 text-sm leading-6 text-zinc-300">
                      {it.summary}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </section>
        ) : null}
      </div>
    </div>
  );
}
