import { formatDriveStatus, formatEligibilityStatus } from "@/lib/formatters";

type Status = "ELIGIBLE" | "INELIGIBLE" | "UNKNOWN" | "active" | "closed" | "cancelled" | "upcoming" | "draft";

const STYLES: Record<string, string> = {
  // Eligibility statuses
  ELIGIBLE:   "bg-success-100 text-success-700 border-success-200",
  INELIGIBLE: "bg-danger-100 text-danger-700 border-danger-200",
  UNKNOWN:    "bg-warning-100 text-warning-700 border-warning-200",
  PENDING:    "bg-blue-100 text-blue-700 border-blue-200",
  
  // Drive statuses
  active:     "bg-success-100 text-success-700 border-success-200",
  closed:     "bg-gray-100 text-gray-600 border-gray-200",
  cancelled:  "bg-danger-100 text-danger-700 border-danger-200",
  upcoming:   "bg-blue-100 text-blue-700 border-blue-200",
  draft:      "bg-gray-100 text-gray-500 border-gray-200",
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = STYLES[status] ?? "bg-gray-100 text-gray-600 border-gray-200";
  
  // Format the status text
  const displayText = status.toUpperCase() === status 
    ? formatEligibilityStatus(status) 
    : formatDriveStatus(status);
  
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border ${cls}`}>
      {displayText}
    </span>
  );
}
