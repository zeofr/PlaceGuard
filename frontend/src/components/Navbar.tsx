"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearAuth, getName, getUSN } from "@/lib/auth";

export default function Navbar() {
  const router = useRouter();
  const [name, setName] = useState<string | null>(null);
  const [usn, setUsn] = useState<string | null>(null);

  useEffect(() => {
    // Only access localStorage on client side
    setName(getName());
    setUsn(getUSN());
  }, []);

  function handleLogout() {
    clearAuth();
    router.push("/login");
  }

  return (
    <nav className="bg-navy-700 border-b border-navy-800 shadow-md">
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Brand */}
          <Link href="/dashboard" className="flex items-center gap-3 group">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-brand-600 shadow-md transition-transform group-hover:scale-105">
              <span className="text-white text-lg font-bold">PG</span>
            </div>
            <div className="flex flex-col">
              <span className="text-white font-bold text-lg leading-tight">PlaceGuard</span>
              <span className="text-navy-300 text-xs">Ramaiah Institute of Technology</span>
            </div>
          </Link>

          {/* Right section */}
          <div className="flex items-center gap-8">
            <Link 
              href="/dashboard" 
              className="text-sm text-navy-200 hover:text-white font-medium transition-colors duration-200"
            >
              Placement Drives
            </Link>

            <div className="flex items-center gap-4">
              <div className="text-sm text-right">
                <div className="text-white font-semibold">{name || "Loading..."}</div>
                {usn && <div className="text-navy-300 text-xs font-mono">{usn}</div>}
              </div>

              <button
                onClick={handleLogout}
                className="text-sm text-navy-300 hover:text-brand-400 font-medium transition-colors duration-200"
              >
                Sign out
              </button>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
