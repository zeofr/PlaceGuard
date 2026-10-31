"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import StatusBadge from "@/components/StatusBadge";
import {
  checkEligibility,
  getDriveTimeline,
  type DriveTimeline,
  type EligibilityResult,
  type TimelineEvent,
} from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import { format } from "date-fns";

// ── authority rank → human label ────────────────────────────────────────────
const AUTHORITY_COLOUR: Record<number, string> = {
  1: "bg-green-100 text-green-800",
  2: "bg-blue-100 text-blue-800",
  3: "bg-indigo-100 text-indigo-800",
  4: "bg-gray-100 text-gray-700",
  5: "bg-orange-100 text-orange-700",
};

function rankLabel(rank: number): string {
  return (
    { 1: "Official PDF", 2: "Placement Cell", 3: "Coordinator", 4: "Portal", 5: "Student" }[rank] ??
    `Rank ${rank}`
  );
}

// ── Timeline event card ──────────────────────────────────────────────────────
function EventCard({ event }: { event: TimelineEvent }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`relative border-l-4 pl-4 pb-6 ${
        event.is_correction ? "border-amber-400" : "border-gray-200"
      }`}
    >
      {/* dot */}
      <div
        className={`absolute -left-2 top-0 w-3.5 h-3.5 rounded-full border-2 border-white ${
          event.is_correction ? "bg-amber-400" : "bg-gray-300"
        }`}
      />

      <div className="flex flex-wrap items-center gap-2 mb-1">
        <span className="text-xs text-gray-400">
          {format(new Date(event.timestamp), "dd MMM yyyy, HH:mm")}
        </span>
        <span
          className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
            AUTHORITY_COLOUR[event.authority_rank] ?? "bg-gray-100"
          }`}
        >
          {event.source_type}
        </span>
        {event.is_correction && (
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">
            Correction
          </span>
        )}
      </div>

      <p className="text-sm font-medium text-gray-800">
        <span className="font-mono text-brand-700">{event.criterion_type}</span>{" "}
        {event.operator}{" "}
        <span className="font-semibold">{event.value}</span>
        {event.scope !== "ALL" && (
          <span className="text-gray-400 ml-1 text-xs">(scope: {event.scope})</span>
        )}
      </p>

      {event.raw_notice_snippet && (
        <button
          onClick={() => setExpanded((p) => !p)}
          className="text-xs text-brand-600 hover:underline mt-1"
        >
          {expanded ? "Hide source notice ↑" : "Show source notice ↓"}
        </button>
      )}
      {expanded && event.raw_notice_snippet && (
        <pre className="mt-2 text-xs bg-gray-50 border border-gray-200 rounded p-3 whitespace-pre-wrap text-gray-600">
          {event.raw_notice_snippet}
        </pre>
      )}
    </div>
  );
}

// ── Eligibility panel ────────────────────────────────────────────────────────
function EligibilityPanel({
  result,
  onCheck,
  loading,
}: {
  result: EligibilityResult | null;
  onCheck: () => void;
  loading: boolean;
}) {
  const statusColour = {
    ELIGIBLE:   "bg-green-50 border-green-200",
    INELIGIBLE: "bg-red-50 border-red-200",
    UNKNOWN:    "bg-yellow-50 border-yellow-200",
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h2 className="font-semibold text-gray-900 mb-4">My Eligibility</h2>

      {!result && (
        <button
          onClick={onCheck}
          disabled={loading}
          className="w-full py-2.5 rounded-lg bg-brand-600 hover:bg-brand-700 text-white font-medium text-sm transition disabled:opacity-60"
        >
          {loading ? "Checking…" : "Check My Eligibility"}
        </button>
      )}

      {result && (
        <div className={`rounded-lg border p-4 ${statusColour[result.status]}`}>
          <div className="flex items-center justify-between mb-3">
            <StatusBadge status={result.status} />
            <span className="text-xs text-gray-500">
              {result.criteria_checked} criteria checked
            </span>
          </div>

          {/* Summary */}
          {result.summary && (
            <p className="text-sm text-gray-700 mb-3">{result.summary}</p>
          )}

          {/* Per-criterion table */}
          <div className="space-y-1.5 mb-3">
            {result.criteria_results.map((cr, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <span
                  className={
                    cr.status === "PASS"
                      ? "text-green-600 font-bold"
                      : cr.status === "FAIL"
                      ? "text-red-600 font-bold"
                      : "text-yellow-600 font-bold"
                  }
                >
                  {cr.status === "PASS" ? "✓" : cr.status === "FAIL" ? "✗" : "?"}
                </span>
                <span className="text-gray-700">{cr.message}</span>
              </div>
            ))}
          </div>

          {/* Registration link */}
          {result.status === "ELIGIBLE" && result.registration_link && (
            <a
              href={result.registration_link}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block mt-2 px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-semibold transition"
            >
              {result.already_registered ? "View Registration Form" : "Register Now →"}
            </a>
          )}

          {/* Full explanation toggle */}
          {result.explanation && (
            <details className="mt-3">
              <summary className="text-xs text-brand-600 cursor-pointer hover:underline">
                Full explanation
              </summary>
              <p className="mt-2 text-xs text-gray-600 bg-white rounded p-3 border border-gray-200 whitespace-pre-wrap">
                {result.explanation}
              </p>
            </details>
          )}

          <button
            onClick={onCheck}
            disabled={loading}
            className="mt-3 text-xs text-gray-400 hover:text-brand-600 transition"
          >
            Re-check
          </button>
        </div>
      )}
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────
export default function DrivePage() {
  const router = useRouter();
  const params = useParams();
  const driveId = params?.driveId as string;

  const [timeline, setTimeline]           = useState<DriveTimeline | null>(null);
  const [eligibility, setEligibility]     = useState<EligibilityResult | null>(null);
  const [timelineLoading, setTLLoading]   = useState(true);
  const [eligLoading, setEligLoading]     = useState(false);
  const [error, setError]                 = useState<string | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) { router.push("/login"); return; }
    loadTimeline();
  }, [driveId]); // eslint-disable-line

  async function loadTimeline() {
    setTLLoading(true);
    try {
      const data = await getDriveTimeline(driveId);
      setTimeline(data);
    } catch {
      setError("Failed to load drive details.");
    } finally {
      setTLLoading(false);
    }
  }

  async function handleCheckEligibility() {
    setEligLoading(true);
    try {
      const result = await checkEligibility(driveId, true);
      setEligibility(result);
    } catch {
      setError("Eligibility check failed.");
    } finally {
      setEligLoading(false);
    }
  }

  if (timelineLoading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="text-center py-20 text-gray-400">Loading drive details…</div>
      </div>
    );
  }

  if (error || !timeline) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="max-w-3xl mx-auto px-4 py-10">
          <p className="text-red-600 bg-red-50 rounded-lg px-4 py-3">{error ?? "Drive not found."}</p>
          <Link href="/dashboard" className="text-sm text-brand-600 mt-4 inline-block hover:underline">
            ← Back to drives
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Back */}
        <Link href="/dashboard" className="text-sm text-brand-600 hover:underline mb-4 inline-block">
          ← All drives
        </Link>

        {/* Drive header */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <div className="flex items-start justify-between flex-wrap gap-3">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{timeline.company_name}</h1>
              {timeline.deadline && (
                <p className="text-sm text-gray-500 mt-1">
                  Deadline:{" "}
                  <span className="font-medium text-gray-700">
                    {format(new Date(timeline.deadline), "dd MMM yyyy, h:mm a")}
                  </span>
                </p>
              )}
            </div>
            <StatusBadge status={timeline.status} />
          </div>

          {/* Current criteria summary */}
          {timeline.current_criteria.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Current Requirements
              </p>
              <div className="flex flex-wrap gap-2">
                {timeline.current_criteria.map((c, i) => (
                  <span
                    key={i}
                    className="text-xs px-3 py-1 rounded-full bg-indigo-50 text-indigo-800 font-mono border border-indigo-100"
                    title={`Source: ${c.source_type} (rank ${c.authority_rank})`}
                  >
                    {c.criterion_type} {c.operator} {c.value}
                    {c.scope !== "ALL" && ` [${c.scope}]`}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Two-column layout: timeline left, eligibility right */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Timeline */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="font-semibold text-gray-900 mb-1">
                Update Timeline
              </h2>
              <p className="text-xs text-gray-400 mb-5">
                {timeline.total_events} event{timeline.total_events !== 1 ? "s" : ""} from all sources — oldest first.
              </p>

              {timeline.timeline.length === 0 ? (
                <p className="text-sm text-gray-400">No events yet.</p>
              ) : (
                <div className="ml-1">
                  {timeline.timeline.map((ev) => (
                    <EventCard key={ev.fact_id} event={ev} />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Eligibility panel */}
          <div>
            <EligibilityPanel
              result={eligibility}
              onCheck={handleCheckEligibility}
              loading={eligLoading}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
