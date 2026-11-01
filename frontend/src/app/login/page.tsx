"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";
import { saveSession } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [usn, setUsn] = useState("");
  const [dob, setDob] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await login(usn.toUpperCase(), dob);
      saveSession(res.access_token, res.usn, res.name);
      router.push("/dashboard");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Login failed. Check your USN and date of birth.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-navy-50 via-gray-50 to-brand-50">
      <div className="w-full max-w-md">
        {/* Main card */}
        <div className="card p-10 shadow-strong">
          {/* Header */}
          <div className="mb-8 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-xl bg-brand-600 shadow-medium mb-4">
              <span className="text-white text-2xl font-bold">PG</span>
            </div>
            <h1 className="text-3xl font-bold text-navy-800 mb-1">PlaceGuard</h1>
            <p className="text-sm text-gray-600">Ramaiah Institute of Technology</p>
            <p className="text-xs text-gray-500 mt-1">Student Placement Portal</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                University Seat Number (USN)
              </label>
              <input
                type="text"
                required
                placeholder="1MS22CS042"
                value={usn}
                onChange={(e) => setUsn(e.target.value.toUpperCase())}
                className="input-field font-mono text-sm uppercase"
                autoComplete="username"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Date of Birth
              </label>
              <input
                type="date"
                required
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                className="input-field"
                autoComplete="bday"
              />
            </div>

            {error && (
              <div className="bg-danger-50 border border-danger-200 text-danger-700 rounded-lg px-4 py-3 text-sm">
                <div className="flex items-start gap-2">
                  <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  <span>{error}</span>
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 text-base shadow-md hover:shadow-lg"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Signing in...
                </span>
              ) : (
                "Sign In"
              )}
            </button>
          </form>

          {/* Footer */}
          <div className="mt-6 pt-6 border-t border-gray-200">
            <p className="text-xs text-center text-gray-500">
              For assistance with login, contact the Training and Placement Office
            </p>
          </div>
        </div>

        {/* Additional info */}
        <div className="mt-4 text-center">
          <p className="text-xs text-gray-600">
            © 2026 Ramaiah Institute of Technology
          </p>
        </div>
      </div>
    </div>
  );
}
