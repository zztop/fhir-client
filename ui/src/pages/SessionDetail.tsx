import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { CardDisplay } from "@/components/crd/CardDisplay";
import { AdaptiveForm } from "@/components/dtr/AdaptiveForm";
import { StaticForm } from "@/components/dtr/StaticForm";
import { StepTimeline, type TimelineStep } from "@/components/layout/StepTimeline";
import { BundleReviewForm } from "@/components/pas/BundleReviewForm";
import { DispositionBadge } from "@/components/pas/DispositionBadge";
import { RawJsonPanel } from "@/components/pas/RawJsonPanel";
import { Banner } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useDevMode } from "@/context/DevModeContext";
import { useInquirePas, usePatchPasBundle, usePreparePas, useSubmitPas } from "@/hooks/usePAS";
import { useNextQuestion, useStartDtr, useSubmitDtr } from "@/hooks/useQuestionnaire";
import { useSession } from "@/hooks/useSession";
import type { AnsweredItem, QuestionItem as QuestionItemType } from "@/types";

export function SessionDetail() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error, refetch } = useSession(id);
  const { devMode } = useDevMode();

  const startDtr = useStartDtr(id ?? "");
  const nextQuestionMutation = useNextQuestion(id ?? "");
  const submitDtr = useSubmitDtr(id ?? "");
  const preparePas = usePreparePas(id ?? "");
  const patchBundle = usePatchPasBundle(id ?? "");
  const submitPas = useSubmitPas(id ?? "");
  const inquirePas = useInquirePas(id ?? "");

  const [adaptiveQuestion, setAdaptiveQuestion] = useState<QuestionItemType | null>(null);
  const [adaptiveDone, setAdaptiveDone] = useState(false);
  const [adaptiveCount, setAdaptiveCount] = useState(0);
  const [pollCount, setPollCount] = useState(0);

  const disposition = data?.pas_submission?.disposition ?? null;

  useEffect(() => {
    if (disposition !== "Pended" || pollCount >= 3) return;
    const timer = setTimeout(() => {
      inquirePas.mutate(undefined, { onSuccess: () => setPollCount((c) => c + 1) });
    }, 10000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disposition, pollCount]);

  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (error || !data) {
    return (
      <div className="flex flex-col gap-3">
        <Banner tone="error">Failed to load session.</Banner>
        <Button className="self-start" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  const { session, crd_result, questionnaire_session, pas_submission } = data;

  const steps: TimelineStep[] = [
    { label: "CRD", status: crd_result ? "complete" : "active" },
    {
      label: "DTR",
      status: !crd_result?.smart_url
        ? "pending"
        : questionnaire_session?.qr_reference
          ? "complete"
          : "active",
    },
    {
      label: "PAS",
      status: !pas_submission ? "pending" : pas_submission.disposition ? "complete" : "active",
    },
  ];

  const canPreparePas =
    crd_result?.pa_needed &&
    (!crd_result.smart_url || Boolean(questionnaire_session?.qr_reference));

  return (
    <div className="grid grid-cols-1 gap-8 md:grid-cols-[240px_1fr]">
      <aside>
        <StepTimeline steps={steps} />
      </aside>

      <div className="flex flex-col gap-8">
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase text-slate-500">CRD Result</h2>

          {crd_result?.pa_needed && (
            <Banner tone="warning">
              Documentation Required — complete the DTR questionnaire before submitting PA
            </Banner>
          )}
          {crd_result && !crd_result.pa_needed && (
            <Banner tone="success">No Prior Authorization Required</Banner>
          )}
          {crd_result?.cards.length === 0 && <Banner tone="info">No CDS cards returned</Banner>}

          <div className="mt-3 flex flex-col gap-3">
            {crd_result?.cards.map((card, i) => (
              <CardDisplay key={i} card={card} />
            ))}
          </div>

          {devMode && crd_result && (
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <RawJsonPanel data={crd_result.hook_request} label="Request sent" />
              <RawJsonPanel data={crd_result.raw_response} label="Response received" />
            </div>
          )}
        </section>

        {crd_result?.smart_url && (
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase text-slate-500">
              DTR Questionnaire
            </h2>

            {!questionnaire_session && (
              <Button
                onClick={() =>
                  startDtr.mutate(undefined, {
                    onSuccess: (res) => {
                      if (res.mode === "adaptive") {
                        setAdaptiveQuestion(res.current_question ?? null);
                        setAdaptiveCount(res.answered_count ?? 0);
                      }
                    },
                  })
                }
                disabled={startDtr.isPending}
              >
                {startDtr.isPending ? "Starting…" : "Start DTR"}
              </Button>
            )}

            {questionnaire_session && !questionnaire_session.qr_reference && (
              <>
                {questionnaire_session.mode === "static" && (
                  <StaticForm
                    questions={questionnaire_session.questionnaire_json.item}
                    submitting={submitDtr.isPending}
                    onSubmit={(items) => submitDtr.mutate(items)}
                  />
                )}
                {questionnaire_session.mode === "adaptive" && (
                  <AdaptiveForm
                    currentQuestion={adaptiveQuestion}
                    answeredCount={adaptiveCount}
                    done={adaptiveDone}
                    submitting={submitDtr.isPending}
                    onNext={(item: AnsweredItem) =>
                      nextQuestionMutation.mutate(item, {
                        onSuccess: (res) => {
                          setAdaptiveQuestion(res.current_question);
                          setAdaptiveDone(res.done);
                          setAdaptiveCount(res.answered_count);
                        },
                      })
                    }
                    onSubmit={() => submitDtr.mutate(undefined)}
                  />
                )}
              </>
            )}

            {questionnaire_session?.qr_reference && (
              <Banner tone="success">
                Documentation submitted ✓ — Reference: {questionnaire_session.qr_reference}
              </Banner>
            )}

            {devMode && questionnaire_session?.qr_reference && (
              <div className="mt-3">
                <RawJsonPanel data={questionnaire_session} label="QuestionnaireResponse" />
              </div>
            )}
          </section>
        )}

        {crd_result?.pa_needed && (
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase text-slate-500">
              PAS Bundle Review & Submit
            </h2>

            {!pas_submission && (
              <Button
                disabled={!canPreparePas || preparePas.isPending}
                onClick={() => preparePas.mutate()}
              >
                {preparePas.isPending ? "Preparing…" : "Prepare PAS Bundle"}
              </Button>
            )}

            {pas_submission && !pas_submission.disposition && (
              <div className="flex flex-col gap-4">
                <BundleReviewForm
                  bundle={pas_submission.bundle_json}
                  qrReference={questionnaire_session?.qr_reference ?? null}
                  onPatch={async (edits) => {
                    await patchBundle.mutateAsync(edits);
                  }}
                />
                <Button
                  className="self-start"
                  disabled={submitPas.isPending}
                  onClick={() => submitPas.mutate()}
                >
                  {submitPas.isPending ? "Submitting to payer…" : "Submit Prior Authorization"}
                </Button>
              </div>
            )}

            {pas_submission?.disposition && (
              <div className="flex flex-col gap-3">
                <DispositionBadge disposition={pas_submission.disposition} />
                {pas_submission.disposition === "Granted" && (
                  <Banner tone="success">
                    Authorization Granted — Auth # {pas_submission.auth_number}
                  </Banner>
                )}
                {pas_submission.disposition === "Denied" && (
                  <Banner tone="error">Prior Authorization Denied</Banner>
                )}
                {pas_submission.disposition === "Pended" && (
                  <div className="flex flex-col gap-2">
                    <Banner tone="warning">
                      {pollCount < 3
                        ? "Awaiting payer decision…"
                        : "Still pending — click Check Status to retry manually"}
                    </Banner>
                    <Button
                      className="self-start"
                      disabled={inquirePas.isPending}
                      onClick={() => inquirePas.mutate()}
                    >
                      Check Status
                    </Button>
                  </div>
                )}
                {devMode && pas_submission.claim_response && (
                  <RawJsonPanel data={pas_submission.claim_response} label="ClaimResponse" />
                )}
              </div>
            )}
          </section>
        )}

        <p className="text-xs text-slate-400">Session {session.id}</p>
      </div>
    </div>
  );
}
