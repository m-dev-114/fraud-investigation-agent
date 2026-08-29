import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Input, Select, Skeleton } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn, formatCurrency, formatDate, riskBadgeClass } from '@/lib/utils';
import { Search, ChevronLeft, ChevronRight } from 'lucide-react';

const PAGE_SIZE = 25;

function riskLevelFromScore(score: number | null | undefined) {
  if (score === null || score === undefined) return null;
  if (score >= 75) return 'critical';
  if (score >= 45) return 'high';
  if (score >= 20) return 'medium';
  return 'low';
}

export default function Transactions() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [investigationStatus, setInvestigationStatus] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortDir, setSortDir] = useState('desc');

  const { data, isLoading, error } = useQuery({
    queryKey: ['transactions', page, search, status, investigationStatus, sortBy, sortDir],
    queryFn: () =>
      api.listTransactions({
        page,
        page_size: PAGE_SIZE,
        search: search || undefined,
        status: status || undefined,
        investigation_status: investigationStatus || undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
      }),
    placeholderData: (prev) => prev,
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  const toggleSort = (col: string) => {
    if (sortBy === col) {
      setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(col);
      setSortDir('desc');
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Transactions</h1>
        <p className="text-muted-foreground text-sm">Search, filter, and open transactions for investigation</p>
      </div>

      <Card>
        <CardContent className="p-4 flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search transaction, customer, merchant, city..."
              className="pl-8"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            />
          </div>
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="pending">Pending</option>
          </Select>
          <Select value={investigationStatus} onChange={(e) => { setInvestigationStatus(e.target.value); setPage(1); }}>
            <option value="">Any investigation status</option>
            <option value="not_started">Not started</option>
            <option value="in_progress">In progress</option>
            <option value="completed">Completed</option>
          </Select>
        </CardContent>
      </Card>

      {error && <div className="text-danger text-sm">Failed to load transactions: {(error as Error).message}</div>}

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-muted-foreground text-xs">
                <th className="text-left font-medium p-3">Transaction</th>
                <th className="text-left font-medium p-3">Customer</th>
                <th className="text-left font-medium p-3 cursor-pointer" onClick={() => toggleSort('amount')}>Amount</th>
                <th className="text-left font-medium p-3">Channel</th>
                <th className="text-left font-medium p-3">Status</th>
                <th className="text-left font-medium p-3 cursor-pointer" onClick={() => toggleSort('risk_score')}>Risk Score</th>
                <th className="text-left font-medium p-3">Investigation</th>
                <th className="text-left font-medium p-3 cursor-pointer" onClick={() => toggleSort('created_at')}>Date</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="border-b border-border/50">
                  <td className="p-3" colSpan={8}><Skeleton className="h-5 w-full" /></td>
                </tr>
              ))}
              {!isLoading && data?.items?.map((t: any) => {
                const level = riskLevelFromScore(t.risk_score);
                return (
                  <tr
                    key={t.id}
                    onClick={() => navigate(`/investigation/${t.id}`)}
                    className="border-b border-border/50 hover:bg-muted/50 cursor-pointer transition-colors"
                  >
                    <td className="p-3 font-mono text-xs">{t.id}</td>
                    <td className="p-3 font-mono text-xs text-muted-foreground">{t.customer_id}</td>
                    <td className="p-3 font-medium">{formatCurrency(t.amount, t.currency)}</td>
                    <td className="p-3 capitalize text-muted-foreground">{t.channel}</td>
                    <td className="p-3">
                      <Badge className={t.status === 'success' ? 'badge-low' : t.status === 'failed' ? 'badge-critical' : 'badge-medium'}>
                        {t.status}
                      </Badge>
                    </td>
                    <td className="p-3">
                      {t.risk_score !== null ? (
                        <Badge className={cn(riskBadgeClass(level))}>{t.risk_score.toFixed(0)} · {level}</Badge>
                      ) : (
                        <span className="text-muted-foreground text-xs">not scored</span>
                      )}
                    </td>
                    <td className="p-3 text-xs text-muted-foreground capitalize">{t.investigation_status.replace('_', ' ')}</td>
                    <td className="p-3 text-xs text-muted-foreground">{formatDate(t.created_at)}</td>
                  </tr>
                );
              })}
              {!isLoading && data?.items?.length === 0 && (
                <tr><td colSpan={8} className="p-6 text-center text-muted-foreground">No transactions match your filters.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between p-3 border-t border-border text-sm">
          <span className="text-muted-foreground">
            {data ? `${data.total.toLocaleString()} transactions` : ''}
          </span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-xs text-muted-foreground">Page {page} of {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
