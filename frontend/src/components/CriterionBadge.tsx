import { formatCriterion } from "@/lib/formatters";

interface CriterionBadgeProps {
  criterionType: string;
  operator: string;
  value: any;
  scope?: string;
  sourceType?: string;
  authorityRank?: number;
}

export default function CriterionBadge({
  criterionType,
  operator,
  value,
  scope,
  sourceType,
  authorityRank,
}: CriterionBadgeProps) {
  const formattedText = formatCriterion(criterionType, operator, value, scope);

  return (
    <div
      className="flex items-start gap-3 p-4 rounded-lg bg-gray-50 border border-gray-200 hover:border-brand-300 transition-colors"
      title={
        sourceType && authorityRank
          ? `Source: ${sourceType} (Authority rank: ${authorityRank})`
          : undefined
      }
    >
      <svg
        className="w-5 h-5 text-brand-600 flex-shrink-0 mt-0.5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <div className="flex-1">
        <p className="text-sm font-semibold text-gray-900 leading-relaxed">{formattedText}</p>
        {scope && scope !== "ALL" && (
          <p className="text-xs text-gray-500 mt-1">Applies to: {scope}</p>
        )}
      </div>
    </div>
  );
}
