import { Badge } from "@/components/ui/badge";
import type { Disposition } from "@/types";

const CONFIG: Record<Disposition, { color: "green" | "red" | "orange"; icon: string }> = {
  Granted: { color: "green", icon: "✓" },
  Denied: { color: "red", icon: "✗" },
  Pended: { color: "orange", icon: "⏱" },
};

export function DispositionBadge({ disposition }: { disposition: Disposition }) {
  const config = CONFIG[disposition];
  return (
    <Badge color={config.color} className="text-sm">
      {config.icon} {disposition}
    </Badge>
  );
}
