import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { SessionStatus } from "@/types";

const STATUS_CONFIG: Record<SessionStatus, { label: string; color: BadgeProps["color"] }> = {
  created: { label: "Created", color: "gray" },
  crd_complete: { label: "CRD Complete", color: "blue" },
  dtr_in_progress: { label: "DTR In Progress", color: "yellow" },
  dtr_complete: { label: "DTR Complete", color: "blue" },
  pas_reviewing: { label: "PAS Reviewing", color: "yellow" },
  pas_submitted: { label: "PAS Submitted", color: "purple" },
  granted: { label: "Granted", color: "green" },
  denied: { label: "Denied", color: "red" },
  pended: { label: "Pended", color: "orange" },
};

export function StatusBadge({ status }: { status: SessionStatus }) {
  const config = STATUS_CONFIG[status];
  return <Badge color={config.color}>{config.label}</Badge>;
}
