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
  const [drives, setDrives]   = useState<Drive[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [filter, setFilter]   = useState<string>("active");

  useEffect(() => {
    if (!isLoggedIn()) { router.push("/login"); return; }
    loadDrives();
  }, [filter]); // eslint-disable-line

  async function loadDrives() {
    setLoading(true);
    setError(null);
    try {
      const data = await listDrives(filter === "all" ? undefined : filter);
      setDrives(data);
    } catch {
      setError("Failed to load drives. Is the API server running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Placement Drives</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Click a drive to see requirements and check your eligibility.
            </p>
          </div>

          {/* Filter tabs */}
          <div className="flex rounded-lg overflow-hidden border border-gray-200">
            {["active", "closed", "all"].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-2 text-sm font-medium transition ${
                  filter === f
                    ? "bg-brand-600 text-white"
                    : "bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* States */}
        {loading && (
          <div className="text-center py-20 text-gray-400">Loading drives…</div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {!loading && !error && drives.length === 0 && (
          <div className="text-center py-20 text-gray-400">
            No {filter} drives found.
          </div>
        )}

        {/* Drive cards */}
        {!loading && !error && drives.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2">
            {drives.map((drive) => (
              <Link
                key={drive.drive_id}
                href={`/drive/${drive.drive_id}`}
                className="block bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md hover:border-brand-300 transition"
              >
                <div className="flex items-start justify-between mb-3">
                  <h2 className="font-semibold text-gray-900 text-lg leading-tight">
                    {drive.company_name}
                  </h2>
                  <StatusBadge status={drive.status} />
                </div>

                {drive.deadline ? (
                  <p className="text-sm text-gray-500">
                    Deadline:{" "}
                    <span className="font-medium text-gray-700">
                      {format(new Date(drive.deadline), "dd MMM yyyy, h:mm a")}
                    </span>
                  </p>
                ) : (
                  <p className="text-sm text-gray-400">No deadline set</p>
                )}

                <p className="text-xs text-brand-600 font-medium mt-3">
                  View eligibility →
                </p>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
