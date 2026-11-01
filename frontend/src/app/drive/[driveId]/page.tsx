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
  type CurrentCriterion,
} from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import { format } from "date-fns";
import { formatCriterion, formatCriterionResult } from "@/lib/formatters";

// ── authority rank → human label ────────────────────────────────────────────
const AUTHORITY_COLOUR: Record<number, string> = {
  1: "bg-success-100 text-success-800 border-success-200",
  2: "bg-blue-100 text-blue-800 border-blue-200",
  3: "bg-indigo-100 text-indigo-800 border-indigo-200",
  4: "bg-gray-100 text-gray-700 border-gray-200",
  5: "bg-warning-100 text-warning-700 border-warning-200",
};

const SOURCE_LABELS: Record<number, string> = {
  1: "Official PDF",
  2: "Placement Cell",
  3: "Coordinator",
  4: "Portal",
  5: "Student Report",
};

function getSourceLabel(sourceType: string, rank: number): string {
  return SOURCE_LABELS[rank] || sourceType;
}

// ── Timeline event card ──────────────────────────────────────────────────────
function EventCard({ event }: { event: TimelineEvent }) {
  const [expanded, setExpanded] = useState(false);
  const formattedCriterion = formatCriterion(
    event.criterion_type,
    event.operator,
    event.value,
    event.scope
  );

  return (
    <div
      className={`relative border-l-4 pl-5 pb-8 ${
        event.is_correction ? "border-warning-400" : "border-gray-300"
      }`}
    >
      {/* Timeline dot */}
      <div
        className={`absolute -left-2.5 top-0 w-4 h-4 rounded-full border-2 border-white shadow-sm ${
          event.is_correction ? "bg-warning-500" : "bg-gray-400"
        }`}
      />

      {/* Event metadata */}
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <span className="text-xs text-gray-500 font-medium">
          {format(new Date(event.timestamp), "dd MMM yyyy, HH:mm")}
        </span>
        <span
          className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${
            AUTHORITY_COLOUR[event.authority_rank] ?? "bg-gray-100 border-gray-200"
          }`}
        >
          {getSourceLabel(event.source_type, event.authority_rank)}
        </span>
        {event.is_correction && (
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-warning-100 text-warning-800 border border-warning-200">
            Correction
          </span>
        )}
      </div>

      {/* Formatted criterion */}
      <p className="text-sm font-semibold text-navy-800">
        {formattedCriterion}
      </p>

      {event.scope !== "ALL" && (
        <p className="text-xs text-gray-500 mt-1">
          Scope: {event.scope}
        </p>
      )}

      {/* Source notice snippet toggle */}
      {event.raw_notice_snippet && (
        <>
          <button
            onClick={() => setExpanded((p) => !p)}
            className="text-xs text-brand-600 hover:text-brand-700 font-medium mt-2 flex items-center gap-1"
          >
            {expanded ? (
              <>
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                </svg>
                Hide source notice
              </>
            ) : (
              <>
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
                Show source notice
              </>
            )}
          </button>
          {expanded && (
            <pre className="mt-3 text-xs bg-gray-50 border border-gray-200 rounded-lg p-4 whitespace-pre-wrap text-gray-700 leading-relaxed">
              {event.raw_notice_snippet}
            </pre>
          )}
        </>
      )}
    </div>
  );
}

// ── Eligibility panel ────────────────────────────────────────────────────────
function EligibilityPanel({
  result,
  onCheck,
  loading,
  error,
}: {
  result: EligibilityResult | null;
  onCheck: () => void;
  loading: boolean;
  error: string | null;
}) {
  const statusConfig: Record<string, { bg: string; border: string; icon: JSX.Element }> = {
    ELIGIBLE: {
      bg: "bg-success-50",
      border: "border-success-200",
      icon: (
        <svg className="w-6 h-6 text-success-600" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
        </svg>
      ),
    },
    INELIGIBLE: {
      bg: "bg-danger-50",
      border: "border-danger-200",
      icon: (
        <svg className="w-6 h-6 text-danger-600" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
        </svg>
      ),
    },
    UNKNOWN: {
      bg: "bg-warning-50",
      border: "border-warning-200",
      icon: (
        <svg className="w-6 h-6 text-warning-600" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
        </svg>
      ),
    },
  };

  return (
    <div className="card p-6 sticky top-6">
      <h2 className="text-xl font-bold text-navy-800 mb-6">My Eligibility</h2>

      {!result && (
        <div>
          <p className="text-sm text-gray-600 mb-4">
            Check if you meet the eligibility requirements for this placement drive
          </p>
          
          {error && (
            <div className="mb-4 bg-danger-50 border border-danger-200 text-danger-700 rounded-lg px-4 py-3 text-sm">
              <div className="flex items-start gap-2">
                <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
                <span>{error}</span>
              </div>
            </div>
          )}
          
          <button
            onClick={onCheck}
            disabled={loading}
            className="btn-primary w-full shadow-md hover:shadow-lg"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Checking eligibility...
              </span>
            ) : (
              "Check My Eligibility"
            )}
          </button>
        </div>
      )}

      {result && (
        <div>
          {/* Status header */}
          {statusConfig[result.status] && (
            <div className={`rounded-lg border p-4 mb-4 ${statusConfig[result.status].bg} ${statusConfig[result.status].border}`}>
              <div className="flex items-center gap-3 mb-3">
                {statusConfig[result.status].icon}
                <div className="flex-1">
                  <StatusBadge status={result.status} />
                </div>
              </div>

            {/* Summary */}
            {result.summary && (
              <p className="text-sm text-gray-800 font-medium">{result.summary}</p>
            )}

            {/* Stats */}
            <div className="flex items-center gap-4 mt-3 text-xs text-gray-600">
              <span>{result.criteria_checked} criteria checked</span>
              {result.criteria_passed > 0 && (
                <span className="text-success-700">{result.criteria_passed} passed</span>
              )}
              {result.criteria_failed > 0 && (
                <span className="text-danger-700">{result.criteria_failed} failed</span>
              )}
            </div>
          </div>
          )}

          {/* Criteria results */}
          <div className="space-y-2 mb-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Requirements Breakdown</h3>
            {result.criteria_results.map((cr, i) => {
              const icon =
                cr.status === "PASS" ? "✓" : cr.status === "FAIL" ? "✗" : "?";
              const iconColor =
                cr.status === "PASS"
                  ? "text-success-600"
                  : cr.status === "FAIL"
                  ? "text-danger-600"
                  : "text-warning-600";

              return (
                <div key={i} className="flex items-start gap-3 text-sm p-2 rounded-lg hover:bg-gray-50">
                  <span className={`font-bold text-lg leading-none ${iconColor}`}>
                    {icon}
                  </span>
                  <span className="text-gray-800 leading-relaxed">{cr.message}</span>
                </div>
              );
            })}
          </div>

          {/* Registration link */}
          {result.status === "ELIGIBLE" && result.registration_link && (
            <a
              href={result.registration_link}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full text-center px-4 py-3 rounded-lg bg-success-600 hover:bg-success-700 text-white text-sm font-semibold shadow-md hover:shadow-lg transition-all"
            >
              {result.already_registered ? "View Registration Form" : "Register Now →"}
            </a>
          )}

          {/* Full explanation toggle */}
          {result.explanation && (
            <details className="mt-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
              <summary className="text-sm text-brand-600 font-medium cursor-pointer hover:text-brand-700">
                View detailed explanation
              </summary>
              <p className="mt-3 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                {result.explanation}
              </p>
            </details>
          )}

          {/* Re-check button */}
          <button
            onClick={onCheck}
            disabled={loading}
            className="mt-4 text-sm text-gray-600 hover:text-brand-600 font-medium transition-colors"
          >
            Re-check eligibility
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

  const [timeline, setTimeline] = useState<DriveTimeline | null>(null);
  const [eligibility, setEligibility] = useState<EligibilityResult | null>(null);
  const [timelineLoading, setTLLoading] = useState(true);
  const [eligLoading, setEligLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.push("/login");
      return;
    }
    loadTimeline();
  }, [driveId]); // eslint-disable-line

  async function loadTimeline() {
    setTLLoading(true);
    try {
      const data = await getDriveTimeline(driveId);
      setTimeline(data);
    } catch {
      setError("Unable to load drive details. Please try again.");
    } finally {
      setTLLoading(false);
    }
  }

  async function handleCheckEligibility() {
    setEligLoading(true);
    setError(null); // Clear any previous errors
    try {
      const result = await checkEligibility(driveId, true);
      setEligibility(result);
    } catch (err: any) {
      console.error("Eligibility check error:", err);
      const errorMessage = 
        err?.response?.data?.detail || 
        err?.message || 
        "Eligibility check failed. Please try again.";
      setError(errorMessage);
    } finally {
      setEligLoading(false);
    }
  }

  if (timelineLoading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="flex flex-col items-center justify-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-gray-200 border-t-brand-600 mb-4"></div>
          <p className="text-gray-500 text-sm">Loading drive details...</p>
        </div>
      </div>
    );
  }

  if (error && !timeline) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="max-w-3xl mx-auto px-6 py-10">
          <div className="card p-6 border-danger-200 bg-danger-50">
            <div className="flex items-start gap-3">
              <svg className="w-6 h-6 text-danger-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <div>
                <h3 className="font-semibold text-danger-800 mb-1">Error Loading Drive</h3>
                <p className="text-sm text-danger-700">{error}</p>
              </div>
            </div>
          </div>
          <Link href="/dashboard" className="inline-block mt-4 text-sm text-brand-600 hover:text-brand-700 font-medium">
            ← Back to all drives
          </Link>
        </div>
      </div>
    );
  }

  if (!timeline) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Back button */}
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 text-sm text-brand-600 hover:text-brand-700 font-medium mb-6 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to all drives
        </Link>

        {/* Drive header */}
        <div className="card p-8 mb-6">
          <div className="flex items-start justify-between flex-wrap gap-4 mb-6">
            <div>
              <h1 className="text-3xl font-bold text-navy-800 mb-2">{timeline.company_name}</h1>
              {timeline.deadline ? (
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span>
                    Application deadline:{" "}
                    <span className="font-semibold text-gray-900">
                      {format(new Date(timeline.deadline), "dd MMM yyyy, h:mm a")}
                    </span>
                  </span>
                </div>
              ) : (
                <p className="text-sm text-gray-500">No deadline specified</p>
              )}
            </div>
            <StatusBadge status={timeline.status} />
          </div>

          {/* Current requirements */}
          {timeline.current_criteria.length > 0 && (
            <div>
              <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide mb-4">
                Current Eligibility Requirements
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {timeline.current_criteria.map((c, i) => {
                  const formattedText = formatCriterion(c.criterion_type, c.operator, c.value, c.scope);
                  return (
                    <div
                      key={i}
                      className="flex items-start gap-3 p-4 rounded-lg bg-gray-50 border border-gray-200 hover:border-brand-300 transition-colors"
                      title={`Source: ${getSourceLabel(c.source_type, c.authority_rank)}`}
                    >
                      <svg className="w-5 h-5 text-brand-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{formattedText}</p>
                        {c.scope !== "ALL" && (
                          <p className="text-xs text-gray-500 mt-1">Applies to: {c.scope}</p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Timeline - left column (2/3 width) */}
          <div className="lg:col-span-2">
            <div className="card p-6">
              <div className="mb-6">
                <h2 className="text-xl font-bold text-navy-800 mb-1">Requirement Updates Timeline</h2>
                <p className="text-sm text-gray-600">
                  {timeline.total_events} update{timeline.total_events !== 1 ? "s" : ""} from various sources · Showing oldest first
                </p>
              </div>

              {timeline.timeline.length === 0 ? (
                <div className="text-center py-12">
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-gray-100 mb-3">
                    <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <p className="text-sm text-gray-500">No timeline events yet</p>
                </div>
              ) : (
                <div className="ml-2">
                  {timeline.timeline.map((ev) => (
                    <EventCard key={ev.fact_id} event={ev} />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Eligibility panel - right column (1/3 width) */}
          <div>
            <EligibilityPanel
              result={eligibility}
              onCheck={handleCheckEligibility}
              loading={eligLoading}
              error={error}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
