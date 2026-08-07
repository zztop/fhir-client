import { Badge } from "@/components/ui/badge";
import type { CoverageInformation } from "@/types";

export function CoverageExtensionBadge({ info }: { info: CoverageInformation }) {
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      <Badge color={info["pa-needed"] ? "yellow" : "green"}>
        {info["pa-needed"] ? "PA Needed" : "No PA Needed"}
      </Badge>
      <Badge color="gray">doc-needed: {info["doc-needed"]}</Badge>
      <Badge color="gray">covered: {info.covered}</Badge>
    </div>
  );
}
