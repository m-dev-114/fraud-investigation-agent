import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn, formatCurrency, formatDate, riskBadgeClass } from '@/lib/utils';
import {
  PlayCircle, CheckCircle2, XCircle, AlertTriangle, Network, ShieldCheck,
  Cpu, Sparkles, Clock,
} from 'lucide-react';

const SEVERITY_ICON_CLASS: Record<string, string> = {
  low: 'text-success', medium: 'text-warning', high: 'text-orange-400', critical: 'text-danger',
};

export default function Investigation() {
  const { transactionId } = useParams<{ transactionId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [notes, setNotes] = useState('');

  const { data: txn, isLoading: txnLoading } = useQuery({
    queryKey: ['transaction', transactionId],
    queryFn: () => api.getTransaction(transactionId!),
    enabled: !!transactionId,
  });

  const runMutation = useMutation({
    mutationFn: (forceRerun: boolean) => api.runInvestigation(transactionId!, forceRerun),
    onSuccess: (inv) => {
      qc.setQueryData(['investigation-for-txn', transactionId], inv);
      qc.invalidateQueries({ queryKey: ['transaction', transactionId] });
    },
  });

  const { data: investigation, isLoading: invLoading } = useQuery({
    queryKey: ['investigation-for-txn', transactionId],
    queryFn: () => api.runInvestigation(transactionId!, false),
    enabled: !!transactionId,
  });

  const { data: events } = useQuery({
    queryKey: ['investigation-events', investigation?.id],
    queryFn: () => api.getInvestigationEvents(investigation!.id),
    enabled: !!investigation?.id,
  });

  const decisionMutation = useMutation({
    mutationFn: (decision: string) => api.decideCase(investigation!.case_id, decision, notes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['investigation-for-txn', transactionId] });
      qc.invalidateQueries({ queryKey: ['transaction', transactionId] });
    },
  });

  if (txnLoading) return <div className="p-6"><Skeleton className="h-96 w-full" /></div>;
  if (!txn) return <div className="p-6 text-muted-foreground">Transaction not found.</div>;

  const loadingInv = invLoading || runMutation.isPending;

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold font-mono">{txn.id}</h1>
          <p className="text-muted-foreground text-sm">
            {txn.customer_name} · {txn.merchant_name} · {formatDate(txn.created_at)}
          </p>
        </div>
        <div className="flex gap-2">
          <Link to={`/network/${txn.id}`}>
            <Button variant="outline" size="sm"><Network className="h-4 w-4" /> Fraud Network</Button>
          </Link>
          {investigation && (
            <Button variant="outline" size="sm" onClick={() => runMutation.mutate(true)} disabled={runMutation.isPending}>
              <PlayCircle className="h-4 w-4" /> Re-run Investigation
            </Button>
          )}
        </div>
      </div>

      {/* Transaction summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryStat label="Amount" value={formatCurrency(txn.amount, txn.currency)} />
        <SummaryStat label="Channel" value={txn.channel} />
        <SummaryStat label="Status" value={txn.status} />
        <SummaryStat label="Location" value={`${txn.txn_city || '—'}, ${txn.txn_country || ''}`} />
      </div>

      {loadingInv && (
        <Card>
          <CardContent className="p-6 flex items-center gap-3 text-muted-foreground">
            <Cpu className="h-5 w-5 animate-pulse" /> Running investigation agents — ML scoring, evidence
            correlation, risk decision...
          </CardContent>
        </Card>
      )}

      {investigation && investigation.status === 'completed' && (
        <>
          {/* Risk score + recommendation */}
          <Card>
            <CardContent className="p-6 flex flex-wrap items-center gap-6">
              <div>
                <div className="text-xs text-muted-foreground mb-1">Risk Score</div>
                <div className={cn('text-4xl font-bold', `risk-${investigation.risk_level}`)}>
                  {investigation.risk_score?.toFixed(0)}<span className="text-lg text-muted-foreground">/100</span>
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Risk Level</div>
                <Badge className={cn('text-sm', riskBadgeClass(investigation.risk_level))}>
                  {investigation.risk_level}
                </Badge>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">ML Fraud Probability</div>
                <div className="text-lg font-medium">
                  {investigation.fraud_probability !== null && investigation.fraud_probability !== undefined
                    ? `${(investigation.fraud_probability * 100).toFixed(1)}%` : '—'}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">AI Recommendation</div>
                <RecommendationBadge value={investigation.recommendation} />
              </div>
              <div className="ml-auto text-xs text-muted-foreground flex items-center gap-1">
                <Sparkles className="h-3.5 w-3.5" />
                {investigation.engine_used === 'llm' ? 'LLM-assisted explanation' : 'Deterministic engine'}
              </div>
            </CardContent>
          </Card>

          {/* Summary / explanation */}
          <Card>
            <CardHeader><CardTitle>Investigation Summary</CardTitle></CardHeader>
            <CardContent className="text-sm leading-relaxed">{investigation.summary}</CardContent>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Evidence */}
            <Card>
              <CardHeader><CardTitle>Evidence ({investigation.evidence?.length || 0})</CardTitle></CardHeader>
              <CardContent className="space-y-2 max-h-96 overflow-y-auto">
                {investigation.evidence?.length === 0 && (
                  <p className="text-sm text-muted-foreground">No risk evidence found — transaction appears normal.</p>
                )}
                {investigation.evidence
                  ?.slice()
                  .sort((a: any, b: any) => b.weight - a.weight)
                  .map((ev: any) => (
                    <div key={ev.id} className="rounded-md border border-border p-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 text-sm font-medium">
                          <AlertTriangle className={cn('h-4 w-4', SEVERITY_ICON_CLASS[ev.severity])} />
                          {ev.title}
                        </div>
                        <Badge className={riskBadgeClass(ev.severity)}>{ev.severity}</Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">{ev.description}</p>
                      <div className="text-[10px] text-muted-foreground mt-1 uppercase tracking-wide">
                        {ev.category} · weight {ev.weight}
                      </div>
                    </div>
                  ))}
              </CardContent>
            </Card>

            {/* Timeline */}
            <Card>
              <CardHeader><CardTitle>Investigation Timeline</CardTitle></CardHeader>
              <CardContent className="space-y-3 max-h-96 overflow-y-auto">
                {events?.map((ev: any) => (
                  <div key={ev.id} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <Clock className="h-3.5 w-3.5 text-muted-foreground mt-0.5" />
                      <div className="w-px flex-1 bg-border" />
                    </div>
                    <div className="pb-2">
                      <div className="text-xs font-medium">{ev.title}</div>
                      <div className="text-[10px] text-muted-foreground uppercase tracking-wide">
                        {ev.step.replace(/_/g, ' ')} · {ev.event_type}
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          {/* Analyst decision */}
          <Card>
            <CardHeader><CardTitle>Analyst Decision</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <textarea
                className="w-full rounded-md border border-border bg-background p-2 text-sm min-h-[70px]"
                placeholder="Notes (optional)..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
              <div className="flex gap-2">
                <Button
                  variant="success"
                  onClick={() => decisionMutation.mutate('approve')}
                  disabled={decisionMutation.isPending || !investigation.case_id}
                >
                  <CheckCircle2 className="h-4 w-4" /> Approve
                </Button>
                <Button
                  variant="danger"
                  onClick={() => decisionMutation.mutate('block')}
                  disabled={decisionMutation.isPending || !investigation.case_id}
                >
                  <XCircle className="h-4 w-4" /> Block
                </Button>
                <Button
                  variant="outline"
                  onClick={() => decisionMutation.mutate('escalate')}
                  disabled={decisionMutation.isPending || !investigation.case_id}
                >
                  <AlertTriangle className="h-4 w-4" /> Escalate
                </Button>
                {investigation.case_id && (
                  <Link to={`/audit/${investigation.case_id}`} className="ml-auto">
                    <Button variant="ghost" size="sm"><ShieldCheck className="h-4 w-4" /> View Audit Trail</Button>
                  </Link>
                )}
              </div>
              {decisionMutation.isSuccess && (
                <div className="text-sm text-success flex items-center gap-1">
                  <CheckCircle2 className="h-4 w-4" /> Decision "{decisionMutation.data.decision}" recorded.
                </div>
              )}
              {!investigation.case_id && (
                <p className="text-xs text-muted-foreground">
                  This transaction scored low risk and no case was opened automatically, so there's nothing
                  pending analyst review — it was auto-approved by the risk engine.
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-sm font-medium mt-1 capitalize">{value}</div>
      </CardContent>
    </Card>
  );
}

function RecommendationBadge({ value }: { value?: string }) {
  if (!value) return <span className="text-muted-foreground">—</span>;
  const map: Record<string, string> = {
    approve: 'badge-low', block: 'badge-critical', escalate: 'badge-medium',
  };
  return <Badge className={cn('text-sm uppercase', map[value] || '')}>{value}</Badge>;
}
