import { useEffect, useRef, useState } from "react";

import { RawJsonPanel } from "@/components/pas/RawJsonPanel";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { PASBundle, PASBundleEdits } from "@/types";

type SaveState = "idle" | "saving" | "saved" | "error";

function findClaim(bundle: PASBundle): Record<string, unknown> | undefined {
  return bundle.entry.find((e) => e.resource.resourceType === "Claim")?.resource;
}

function readRef(resource: Record<string, unknown> | undefined): string {
  const ref = (resource as { reference?: string } | undefined)?.reference;
  return ref ?? "—";
}

export function BundleReviewForm({
  bundle,
  onPatch,
  qrReference,
}: {
  bundle: PASBundle;
  onPatch: (edits: PASBundleEdits) => Promise<void>;
  qrReference: string | null;
}) {
  const claim = findClaim(bundle) ?? {};
  const item = (claim.item as { productOrService?: { coding?: { code?: string; system?: string }[] }; quantity?: { value?: number } }[] | undefined)?.[0];
  const coding = item?.productOrService?.coding?.[0];
  const diagnosis = (claim.diagnosis as { diagnosisCodeableConcept?: { coding?: { code?: string }[] } }[] | undefined)?.[0];
  const priority = (claim.priority as { coding?: { code?: string }[] } | undefined)?.coding?.[0]?.code ?? "normal";

  const [diagnosisCode, setDiagnosisCode] = useState(diagnosis?.diagnosisCodeableConcept?.coding?.[0]?.code ?? "");
  const [serviceCode, setServiceCode] = useState(coding?.code ?? "");
  const [serviceSystem, setServiceSystem] = useState(coding?.system ?? "");
  const [quantity, setQuantity] = useState(item?.quantity?.value ?? 1);
  const [priorityValue, setPriorityValue] = useState(priority);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const schedulePatch = (edits: PASBundleEdits) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    setSaveState("saving");
    debounceRef.current = setTimeout(async () => {
      try {
        await onPatch(edits);
        setSaveState("saved");
      } catch {
        setSaveState("error");
      }
    }, 500);
  };

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
  }, []);

  const SAVE_LABEL: Record<SaveState, string> = {
    idle: "",
    saving: "Saving…",
    saved: "Saved ✓",
    error: "Save failed ✗",
  };

  return (
    <Tabs defaultValue="fields">
      <div className="flex items-center justify-between">
        <TabsList>
          <TabsTrigger value="fields">Edit Fields</TabsTrigger>
          <TabsTrigger value="json">Raw JSON</TabsTrigger>
        </TabsList>
        {saveState !== "idle" && (
          <span
            className={`text-xs ${saveState === "error" ? "text-red-600" : "text-slate-500"}`}
          >
            {SAVE_LABEL[saveState]}
          </span>
        )}
      </div>

      <TabsContent value="fields">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Patient" value={readRef(claim.patient as Record<string, unknown>)} readOnly />
          <Field label="Coverage" value={readRef((claim.insurance as { coverage?: Record<string, unknown> }[] | undefined)?.[0]?.coverage)} readOnly />
          <Field label="Practitioner" value={readRef(claim.provider as Record<string, unknown>)} readOnly />
          <Field label="Payer" value={readRef(claim.insurer as Record<string, unknown>)} readOnly />

          <Field
            label="Diagnosis Code"
            value={diagnosisCode}
            onChange={(v) => {
              setDiagnosisCode(v);
              schedulePatch({ diagnosis_code: v });
            }}
          />
          <Field
            label="Service Code"
            value={serviceCode}
            onChange={(v) => {
              setServiceCode(v);
              schedulePatch({ service_code: v });
            }}
          />
          <Field
            label="Service System"
            value={serviceSystem}
            onChange={(v) => {
              setServiceSystem(v);
              schedulePatch({ service_system: v });
            }}
          />
          <div className="flex flex-col gap-1.5">
            <label htmlFor="pas-quantity" className="text-sm font-medium text-slate-800 dark:text-slate-200">
              Quantity
            </label>
            <Input
              id="pas-quantity"
              type="number"
              value={quantity}
              onChange={(e) => {
                const v = Number(e.target.value);
                setQuantity(v);
                schedulePatch({ quantity: v });
              }}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="pas-priority" className="text-sm font-medium text-slate-800 dark:text-slate-200">
              Priority
            </label>
            <Select
              id="pas-priority"
              value={priorityValue}
              onChange={(e) => {
                const v = e.target.value as PASBundleEdits["priority"];
                setPriorityValue(e.target.value);
                schedulePatch({ priority: v });
              }}
            >
              <option value="normal">normal</option>
              <option value="stat">stat</option>
              <option value="deferred">deferred</option>
            </Select>
          </div>
          <Field label="QR Reference" value={qrReference ?? "—"} readOnly />
        </div>
      </TabsContent>

      <TabsContent value="json">
        <RawJsonPanel data={bundle} label="PAS Bundle" />
      </TabsContent>
    </Tabs>
  );
}

function Field({
  label,
  value,
  onChange,
  readOnly,
}: {
  label: string;
  value: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
}) {
  const id = `pas-field-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-slate-800 dark:text-slate-200">
        {label}
      </label>
      <Input
        id={id}
        value={value}
        readOnly={readOnly}
        disabled={readOnly}
        onChange={(e) => onChange?.(e.target.value)}
      />
    </div>
  );
}
