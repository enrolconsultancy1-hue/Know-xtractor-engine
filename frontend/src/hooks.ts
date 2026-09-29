import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { AnalysisStatus, KnowledgePackage } from "./types";

export function useKnowledge(projectId: number | null) {
  const [pkg, setPkg] = useState<KnowledgePackage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError("");
    try {
      setPkg(await api.getKnowledge(projectId));
    } catch (e) {
      setError((e as Error).message);
      setPkg(null);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  return { pkg, loading, error, reload: load };
}

export function useAnalysisPoll(analysisId: number | null) {
  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!analysisId) return;
    let cancelled = false;
    let es: EventSource | null = null;

    const fallbackPoll = () => {
      if (cancelled) return;
      const poll = async () => {
        try {
          const s = await api.getAnalysis(analysisId);
          if (!cancelled) setStatus(s);
          if (s && !["done", "failed", "cancelled"].includes(s.status)) {
            timer.current = window.setTimeout(poll, 1200);
          }
        } catch {
          if (!cancelled) timer.current = window.setTimeout(poll, 2500);
        }
      };
      poll();
    };

    const startStream = () => {
      if (typeof EventSource === "undefined") {
        fallbackPoll();
        return;
      }

      try {
        es = new EventSource(`/api/analysis/${analysisId}/stream`);

        const handleUpdate = (ev: MessageEvent) => {
          if (cancelled) return;
          try {
            const data = JSON.parse(ev.data);
            setStatus((prev) => ({
              id: analysisId,
              project_id: prev?.project_id ?? 0,
              status: data.status,
              stage: data.stage ?? prev?.stage ?? "",
              progress: data.progress ?? prev?.progress ?? 0.0,
              errors: data.errors ?? prev?.errors ?? [],
              warnings: prev?.warnings ?? [],
              summary: data.summary ?? prev?.summary ?? null,
            }));
            if (["done", "failed", "cancelled"].includes(data.status)) {
              es?.close();
            }
          } catch {
            /* ignore parse error */
          }
        };

        es.addEventListener("progress", handleUpdate);
        es.addEventListener("status", handleUpdate);
        es.addEventListener("done", (ev) => {
          handleUpdate(ev);
          es?.close();
        });

        es.onerror = () => {
          es?.close();
          es = null;
          fallbackPoll();
        };
      } catch {
        fallbackPoll();
      }
    };

    const fetchInitial = async () => {
      try {
        const s = await api.getAnalysis(analysisId);
        if (!cancelled) setStatus(s);
        if (s && ["done", "failed", "cancelled"].includes(s.status)) {
          return;
        }
        startStream();
      } catch {
        fallbackPoll();
      }
    };

    fetchInitial();

    return () => {
      cancelled = true;
      if (es) es.close();
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [analysisId]);

  return status;
}

