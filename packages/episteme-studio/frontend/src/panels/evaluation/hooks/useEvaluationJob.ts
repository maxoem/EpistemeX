import { useState, useEffect, useCallback, useRef } from "react";
import { apiClient } from "../../../api/client";
import { subscribeToEvaluationJobEvents } from "../../../api/sse";
import type { EvaluationJobDescriptor, EvaluationJobStatus, StudioEvent } from "../../../api/types";

export interface UseEvaluationJobOptions {
  jobId: string | null;
  onCompleted?: (reportId: string, descriptor: EvaluationJobDescriptor) => void;
  onError?: (error: string) => void;
}

export interface UseEvaluationJobReturn {
  jobId: string | null;
  status: EvaluationJobStatus;
  progress: number;
  currentStage: string;
  events: StudioEvent[];
  error: string | null;
  reportId: string | null;
  report: any | null;
  isCancelling: boolean;
  cancelJob: () => Promise<void>;
}

export function useEvaluationJob({
  jobId,
  onCompleted,
  onError,
}: UseEvaluationJobOptions): UseEvaluationJobReturn {
  const [status, setStatus] = useState<EvaluationJobStatus>("pending");
  const [progress, setProgress] = useState(0);
  const [currentStage, setCurrentStage] = useState("Initializing evaluation job...");
  const [events, setEvents] = useState<StudioEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [reportId, setReportId] = useState<string | null>(null);
  const [report, setReport] = useState<any | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);

  const lastSeqRef = useRef<number>(0);

  const fetchJobStatus = useCallback(
    async (id: string) => {
      try {
        const desc = await apiClient.getEvaluationJob(id);
        setStatus(desc.status);
        if (desc.report_id) {
          setReportId(desc.report_id);
        }
        if (desc.report) {
          setReport(desc.report);
        }
        if (desc.error) {
          setError(desc.error);
        }
        if (desc.status === "completed" && desc.report_id) {
          setProgress(100);
          setCurrentStage("Evaluation completed");
          onCompleted?.(desc.report_id, desc);
        } else if (desc.status === "failed") {
          setError(desc.error || "Evaluation failed");
          onError?.(desc.error || "Evaluation failed");
        }
      } catch (e: any) {
        console.warn("Failed to poll evaluation job:", e);
      }
    },
    [onCompleted, onError]
  );

  useEffect(() => {
    if (!jobId) {
      setStatus("pending");
      setProgress(0);
      setCurrentStage("Ready");
      setEvents([]);
      setError(null);
      setReportId(null);
      setReport(null);
      return;
    }

    fetchJobStatus(jobId);

    const unsubscribe = subscribeToEvaluationJobEvents(
      jobId,
      {
        onEvent: (event) => {
          if (event.seq > lastSeqRef.current) {
            lastSeqRef.current = event.seq;
          }
          setEvents((prev) => [...prev, event]);

          if (event.kind === "evaluation.job.started") {
            setStatus("running");
            setProgress(10);
            setCurrentStage("Job started");
          } else if (event.kind === "evaluation.stage.started") {
            setStatus("running");
            setCurrentStage(event.message || "Stage started");
            setProgress((p) => Math.min(Math.max(p, 25), 85));
          } else if (event.kind === "evaluation.stage.completed") {
            setProgress((p) => Math.min(p + 20, 90));
            setCurrentStage(event.message || "Stage completed");
          } else if (event.kind === "evaluation.query.ranked") {
            setProgress((p) => Math.min(p + 10, 95));
            setCurrentStage("Competency queries evaluated");
          } else if (event.kind === "evaluation.job.completed") {
            setStatus("completed");
            setProgress(100);
            setCurrentStage("Evaluation completed successfully");
            const repId = event.payload?.evaluation_id || null;
            if (repId) {
              setReportId(repId);
            }
            fetchJobStatus(jobId);
          } else if (event.kind === "evaluation.job.failed") {
            setStatus("failed");
            setError(event.payload?.error || event.message);
            setCurrentStage("Evaluation failed");
            fetchJobStatus(jobId);
          } else if (event.kind === "evaluation.job.aborted") {
            setStatus("aborted");
            setCurrentStage("Evaluation cancelled");
            fetchJobStatus(jobId);
          }
        },
        onError: () => {
          fetchJobStatus(jobId);
        },
      },
      lastSeqRef.current
    );

    const pollInterval = setInterval(() => {
      if (status !== "completed" && status !== "failed" && status !== "aborted") {
        fetchJobStatus(jobId);
      }
    }, 3000);

    return () => {
      unsubscribe();
      clearInterval(pollInterval);
    };
  }, [jobId, fetchJobStatus, status]);

  const cancelJob = useCallback(async () => {
    if (!jobId || isCancelling) return;
    try {
      setIsCancelling(true);
      await apiClient.cancelEvaluationJob(jobId);
      setStatus("aborted");
      setCurrentStage("Evaluation cancelled by user");
    } catch (e: any) {
      console.error("Failed to cancel evaluation job:", e);
    } finally {
      setIsCancelling(false);
    }
  }, [jobId, isCancelling]);

  return {
    jobId,
    status,
    progress,
    currentStage,
    events,
    error,
    reportId,
    report,
    isCancelling,
    cancelJob,
  };
}
