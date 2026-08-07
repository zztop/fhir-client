import { useState } from "react";

import { CoverageExtensionBadge } from "@/components/crd/CoverageExtensionBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { Card as CDSCard } from "@/types";

const BORDER_CLASSES: Record<CDSCard["indicator"], string> = {
  info: "border-l-blue-500",
  warning: "border-l-amber-500",
  critical: "border-l-red-500",
};

const INDICATOR_COLOR: Record<CDSCard["indicator"], "blue" | "yellow" | "red"> = {
  info: "blue",
  warning: "yellow",
  critical: "red",
};

export function CardDisplay({ card }: { card: CDSCard }) {
  const [expanded, setExpanded] = useState(false);
  const detail = card.detail ?? "";
  const isLong = detail.length > 200;
  const coverageInfo = card.extension?.["davinci-crd.coverage-information"]?.[0];
  const smartLinks = (card.links ?? []).filter((link) => link.type === "smart");

  return (
    <Card className={`border-l-4 ${BORDER_CLASSES[card.indicator]}`}>
      <CardContent>
        <div className="flex items-start gap-2">
          <Badge color={INDICATOR_COLOR[card.indicator]}>{card.indicator}</Badge>
          <p className="font-semibold text-slate-900 dark:text-slate-100">{card.summary}</p>
        </div>

        {detail && (
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            {isLong && !expanded ? `${detail.slice(0, 200)}…` : detail}
            {isLong && (
              <button
                type="button"
                className="ml-1 text-blue-600 hover:underline"
                onClick={() => setExpanded((v) => !v)}
              >
                {expanded ? "Show less" : "Show more"}
              </button>
            )}
          </p>
        )}

        {card.source.url ? (
          <a
            href={card.source.url}
            target="_blank"
            rel="noreferrer"
            className="mt-2 inline-block text-xs text-blue-600 hover:underline"
          >
            {card.source.label}
          </a>
        ) : (
          <p className="mt-2 text-xs text-slate-400">{card.source.label}</p>
        )}

        {coverageInfo && <CoverageExtensionBadge info={coverageInfo} />}

        {smartLinks.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {smartLinks.map((link) => (
              <span
                key={link.url}
                className="rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
              >
                Launch DTR → {link.label}
              </span>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
