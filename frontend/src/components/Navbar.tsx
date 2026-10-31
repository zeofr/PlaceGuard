"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearSession, getName, getUSN } from "@/lib/auth";

export default function Navbar() {
  const router = useRouter();
  const name = getName();
  const usn  = getUSN();

  function handleLogout() {
    clearSession();
    router.push("/login");
  }

  return (
    <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
      <Link href="/dashboard" className="flex items-center gap-2 font-bold text-brand-700 text-lg">
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-brand-600 text-white text-sm font-bold">PG</span>
        PlaceGuard
      </Link>

      <div className="flex items-center gap-6">
        <Link href="/dashboard" className="text-sm text-gray-600 hover:text-brand-700 font-medium">
          Drives
        </Link>

        <div className="text-sm text-gray-700">
          <span className="font-semibold">{name}</span>
          <span className="text-gray-400 ml-1 font-mono text-xs">({usn})</span>
        </div>

        <button
          onClick={handleLogout}
          className="text-sm text-gray-500 hover:text-red-600 font-medium transition"
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
