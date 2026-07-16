import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getHistory,
  getHistoryDetail,
  getMetrics,
  getPendingReports,
  getRuns,
  getTimeline,
  postTriage,
  runReports,
} from "./client";
import type { TriageInput } from "./types";

export function useTriage() {
  return useMutation({ mutationFn: (input: TriageInput) => postTriage(input) });
}

export function useRuns() {
  return useQuery({ queryKey: ["runs"], queryFn: getRuns, refetchInterval: 30_000 });
}

export function useHistory() {
  return useQuery({ queryKey: ["history"], queryFn: getHistory, refetchInterval: 30_000 });
}

export function useHistoryDetail(runId: string | null) {
  return useQuery({
    queryKey: ["history", runId],
    queryFn: () => getHistoryDetail(runId as string),
    enabled: runId != null,
  });
}

export function useMetrics() {
  return useQuery({ queryKey: ["metrics"], queryFn: getMetrics, refetchInterval: 30_000 });
}

export function useTimeline(granularity: "day" | "hour" = "day") {
  return useQuery({
    queryKey: ["timeline", granularity],
    queryFn: () => getTimeline(granularity),
    refetchInterval: 30_000,
  });
}

export function usePendingReports() {
  return useQuery({
    queryKey: ["pendingReports"],
    queryFn: getPendingReports,
    refetchInterval: 30_000,
  });
}

export function useRunReports() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (limit: number | null) => runReports(limit),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reportsStatus"] });
    },
  });
}
