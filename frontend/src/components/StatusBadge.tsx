type Status = "ELIGIBLE" | "INELIGIBLE" | "UNKNOWN" | "active" | "closed" | "cancelled";

const STYLES: Record<string, string> = {
  ELIGIBLE:   "bg-green-100 text-green-800",
  INELIGIBLE: "bg-red-100 text-red-800",
  UNKNOWN:    "bg-yellow-100 text-yellow-800",
  active:     "bg-green-100 text-green-700",
  closed:     "bg-gray-100 text-gray-600",
  cancelled:  "bg-red-100 text-red-600",
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = STYLES[status] ?? "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${cls}`}>
      {status}
    </span>
  );
}
