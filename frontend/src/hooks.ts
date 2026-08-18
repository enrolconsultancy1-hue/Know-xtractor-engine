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
    const poll = async () => {
      try {
        const s = await api.getAnalysis(analysisId);
        if (!cancelled) setStatus(s);
        if (s && !["done", "failed", "cancelled"].includes(s.status)) {
          timer.current = window.setTimeout(poll, 1200);
        }
      } catch {
        /* ignore transient */
      }
    };
    poll();
    return () => {
      cancelled = true;
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [analysisId]);

  return status;
}
