const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<any>('/api/health'),
  dashboardSummary: () => request<any>('/api/dashboard/summary'),
  listTransactions: (params: Record<string, string | number | undefined>) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== '') as [string, string][]
    );
    return request<any>(`/api/transactions?${q.toString()}`);
  },
  getTransaction: (id: string) => request<any>(`/api/transactions/${id}`),
  runInvestigation: (transactionId: string, forceRerun = false) =>
    request<any>(`/api/investigations/${transactionId}/run`, {
      method: 'POST',
      body: JSON.stringify({ force_rerun: forceRerun }),
    }),
  getInvestigation: (id: string) => request<any>(`/api/investigations/${id}`),
  getInvestigationEvents: (id: string) => request<any>(`/api/investigations/${id}/events`),
  getNetwork: (transactionId: string) => request<any>(`/api/network/${transactionId}`),
  decideCase: (caseId: string, decision: string, notes: string, analystName = 'demo_analyst') =>
    request<any>(`/api/cases/${caseId}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision, notes, analyst_name: analystName }),
    }),
  getAuditTrail: (caseId: string) => request<any>(`/api/audit/${caseId}`),
  getModelMetrics: () => request<any>('/api/model/metrics'),
  getDemoCases: () => request<any>('/api/demo/cases'),
};

export { API_BASE };
