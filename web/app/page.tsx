"use client";

import { useState } from "react";

interface Finding {
  analyzer: string;
  title: string;
  evidence: Record<string, unknown>;
  detail: string;
}

interface Report {
  question: string;
  findings: Finding[];
  root_cause: string;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  recommendation: string;
}

type StreamEvent =
  | { type: "progress"; step: string }
  | { type: "report"; report: Report }
  | { type: "error"; message: string };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const CONFIDENCE_STYLES: Record<Report["confidence"], string> = {
  HIGH: "bg-emerald-100 text-emerald-800 border-emerald-300",
  MEDIUM: "bg-amber-100 text-amber-800 border-amber-300",
  LOW: "bg-red-100 text-red-800 border-red-300",
};

export default function Page() {
  const [question, setQuestion] = useState("Why is /api/search slow?");
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<string[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runInvestigation() {
    setRunning(true);
    setSteps([]);
    setReport(null);
    setError(null);

    try {
      const createResponse = await fetch(`${API_BASE}/investigations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: "demo", question }),
      });

      if (!createResponse.ok) {
        throw new Error(`Failed to start investigation (${createResponse.status})`);
      }

      const { id } = (await createResponse.json()) as { id: string };
      const eventSource = new EventSource(`${API_BASE}/investigations/${id}/events`);

      eventSource.onmessage = (event) => {
        const payload = JSON.parse(event.data) as StreamEvent;

        if (payload.type === "progress") {
          setSteps((prev) => [...prev, payload.step]);
        } else if (payload.type === "report") {
          setReport(payload.report);
          setRunning(false);
          eventSource.close();
        } else if (payload.type === "error") {
          setError(payload.message);
          setRunning(false);
          eventSource.close();
        }
      };

      eventSource.onerror = () => {
        setError("Connection to OpsPilot API was lost.");
        setRunning(false);
        eventSource.close();
      };
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setRunning(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">OpsPilot</h1>
        <p className="text-sm text-neutral-500">
          AI-powered production incident investigator. Ask your infrastructure why it is broken.
        </p>
      </header>

      <section className="flex flex-col gap-3 sm:flex-row">
        <input
          className="flex-1 rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Why is this slow?"
          disabled={running}
        />
        <button
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          onClick={runInvestigation}
          disabled={running}
        >
          {running ? "Investigating..." : "Investigate"}
        </button>
      </section>

      {steps.length > 0 && (
        <section className="flex flex-col gap-1 rounded-md border border-neutral-200 p-4 text-sm">
          {steps.map((step, index) => (
            <div key={index} className="flex items-center gap-2 text-neutral-700">
              <span className="text-emerald-600">✓</span>
              {step}
            </div>
          ))}
        </section>
      )}

      {error && (
        <section className="rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800">
          {error}
        </section>
      )}

      {report && (
        <section className="flex flex-col gap-6">
          <div>
            <h2 className="text-sm font-medium text-neutral-500">Root cause</h2>
            <p className="mt-1 text-base">{report.root_cause}</p>
          </div>

          <div className="flex flex-col gap-3">
            {report.findings.map((finding, index) => (
              <div key={index} className="rounded-md border border-neutral-200 p-4">
                <div className="text-sm font-medium">
                  Finding #{index + 1}: {finding.title}{" "}
                  <span className="text-neutral-400">(via {finding.analyzer})</span>
                </div>
                <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs text-neutral-600">
                  {Object.entries(finding.evidence).map(([key, value]) => (
                    <div key={key} className="contents">
                      <dt className="font-mono text-neutral-400">{key}</dt>
                      <dd className="break-all font-mono">{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <span
              className={`rounded-full border px-3 py-1 text-xs font-medium ${CONFIDENCE_STYLES[report.confidence]}`}
            >
              Confidence: {report.confidence}
            </span>
          </div>

          <div>
            <h2 className="text-sm font-medium text-neutral-500">Recommendation</h2>
            <p className="mt-1 text-base">{report.recommendation}</p>
          </div>
        </section>
      )}
    </main>
  );
}
