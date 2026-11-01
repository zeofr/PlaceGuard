"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import StatusBadge from "@/components/StatusBadge";
import { listDrives, type Drive } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import { format } from "date-fns";

export default function DashboardPage() {
  const router = useRouter();
  const [drives, setDrives] = useState<Drive[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("active");

  useEffect(() => {
    if (!isLoggedIn()) {
      router.push("/login");
      return;
    }
    loadDrives();
  }, [filter]); // eslint-disable-line

  async function loadDrives() {
    setLoading(true);
    setError(null);
    try {
      const data = await listDrives(filter === "all" ? undefined : filter);
      setDrives(data);
    } catch {
      setError("Unable to load placement drives. Please check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }

  const filterOptions = [
    { value: "active", label: "Active Drives", count: 0 },
    { value: "closed", label: "Closed Drives", count: 0 },
    { value: "all", label: "All Drives", count: 0 },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Page header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-navy-800 mb-2">
            Placement Drives
          </h1>
          <p className="text-gray-600">
            Browse upcoming opportunities and check your eligibility for placement drives
          </p>
        </div>

        {/* Filter tabs */}
        <div className="mb-6">
          <div className="inline-flex rounded-lg overflow-hidden border border-gray-300 shadow-soft bg-white">
            {filterOptions.map((option) => (
              <button
                key={option.value}
                onClick={() => setFilter(option.value)}
                className={`px-6 py-3 text-sm font-semibold transition-colors duration-200 ${
                  filter === option.value
                    ? "bg-brand-600 text-white"
                    : "bg-white text-gray-700 hover:bg-gray-50"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Loading state */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-gray-200 border-t-brand-600 mb-4"></div>
            <p className="text-gray-500 text-sm">Loading placement drives...</p>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="card p-6 border-danger-200 bg-danger-50">
            <div className="flex items-start gap-3">
              <svg className="w-6 h-6 text-danger-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <div>
                <h3 className="font-semibold text-danger-800 mb-1">Error Loading Drives</h3>
                <p className="text-sm text-danger-700">{error}</p>
                <button
                  onClick={loadDrives}
                  className="mt-3 text-sm font-medium text-danger-700 hover:text-danger-800 underline"
                >
                  Try again
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && drives.length === 0 && (
          <div className="card p-12 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-100 mb-4">
              <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              No {filter !== "all" ? filter : ""} placement drives found
            </h3>
            <p className="text-sm text-gray-600 max-w-md mx-auto">
              {filter === "active"
                ? "There are currently no active placement drives. Check back later for new opportunities."
                : filter === "closed"
                ? "No closed drives to display."
                : "No drives have been posted yet."}
            </p>
          </div>
        )}

        {/* Drive cards grid */}
        {!loading && !error && drives.length > 0 && (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {drives.map((drive) => (
              <Link
                key={drive.drive_id}
                href={`/drive/${drive.drive_id}`}
                className="card p-6 hover:shadow-medium hover:border-brand-300 transition-all duration-200 group"
              >
                {/* Company name and status */}
                <div className="flex items-start justify-between mb-4">
                  <h2 className="font-bold text-navy-800 text-lg leading-tight group-hover:text-brand-600 transition-colors">
                    {drive.company_name}
                  </h2>
                  <StatusBadge status={drive.status} />
                </div>

                {/* Deadline */}
                {drive.deadline ? (
                  <div className="mb-4">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                      Application Deadline
                    </p>
                    <p className="text-sm font-semibold text-gray-900">
                      {format(new Date(drive.deadline), "dd MMM yyyy")}
                    </p>
                    <p className="text-xs text-gray-600">
                      {format(new Date(drive.deadline), "h:mm a")}
                    </p>
                  </div>
                ) : (
                  <div className="mb-4">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                      Application Deadline
                    </p>
                    <p className="text-sm text-gray-400">Not specified</p>
                  </div>
                )}

                {/* Description preview */}
                {drive.description && (
                  <p className="text-sm text-gray-600 line-clamp-2 mb-4">
                    {drive.description}
                  </p>
                )}

                {/* CTA */}
                <div className="flex items-center gap-2 text-brand-600 text-sm font-semibold group-hover:gap-3 transition-all">
                  <span>View details & check eligibility</span>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
