import type {
  AggregateMetrics,
  HistoryDetail,
  HistoryPage,
  PendingReports,
  RunReportsResponse,
  ReportsStatusResponse,
  RunsPage,
  TimelinePoint,
  TriageInput,
  TriageOutput,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.error ?? body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(resp.status, `${detail}`);
  }
  return (await resp.json()) as T;
}

export function postTriage(input: TriageInput): Promise<TriageOutput> {
  return request<TriageOutput>("/triage", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getRuns(): Promise<RunsPage> {
  return request<RunsPage>("/runs");
}

export function getHistory(): Promise<HistoryPage> {
  return request<HistoryPage>("/history");
}

export function getHistoryDetail(runId: string): Promise<HistoryDetail> {
  return request<HistoryDetail>(`/history/${runId}`);
}

export function getPendingReports(): Promise<PendingReports> {
  return request<PendingReports>("/reports/pending");
}

export function runReports(limit: number | null): Promise<RunReportsResponse> {
  return request<RunReportsResponse>("/reports/run", {
    method: "POST",
    body: JSON.stringify({ limit }),
  });
}

export function getReportsStatus(): Promise<ReportsStatusResponse> {
  return request<ReportsStatusResponse>("/reports/status");
}

export function getMetrics(): Promise<AggregateMetrics> {
  return request<AggregateMetrics>("/metrics");
}

export function getTimeline(granularity: "day" | "hour" = "day"): Promise<TimelinePoint[]> {
  return request<TimelinePoint[]>(`/metrics/timeline?granularity=${granularity}`);
}
