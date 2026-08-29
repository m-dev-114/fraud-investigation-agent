import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, PieChart, Pie, Cell, Legend,
} from 'recharts';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { cn, formatCurrency, riskBadgeClass } from '@/lib/utils';
import { AlertTriangle, ShieldAlert, TrendingUp, IndianRupee } from 'lucide-react';

const RISK_COLORS: Record<string, string> = {
  low: '#22c55e', medium: '#eab308', high: '#f97316', critical: '#ef4444',
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: api.dashboardSummary,
  });

  if (error) {
    return <div className="p-6 text-danger">Failed to load dashboard: {(error as Error).message}</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-muted-foreground text-sm">Real-time fraud monitoring overview</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
        <StatCard label="Total Transactions" value={data?.total_transactions?.toLocaleString()} icon={TrendingUp} loading={isLoading} />
        <StatCard label="Flagged" value={data?.flagged_transactions?.toLocaleString()} icon={AlertTriangle} loading={isLoading} accent="text-warning" />
        <StatCard label="Critical" value={data?.critical_transactions?.toLocaleString()} icon={ShieldAlert} loading={isLoading} accent="text-danger" />
        <StatCard label="Fraud Rate" value={data ? `${(data.fraud_rate * 100).toFixed(2)}%` : undefined} icon={AlertTriangle} loading={isLoading} />
        <StatCard label="Amount at Risk" value={data ? formatCurrency(data.amount_at_risk) : undefined} icon={IndianRupee} loading={isLoading} accent="text-danger" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>Transactions & Fraud (last 30 days)</CardTitle></CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-64 w-full" /> : (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={data?.transactions_by_day}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(220 15% 18%)" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="hsl(215 12% 60%)" />
                  <YAxis tick={{ fontSize: 11 }} stroke="hsl(215 12% 60%)" />
                  <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', fontSize: 12 }} />
                  <Line type="monotone" dataKey="count" stroke="#38bdf8" strokeWidth={2} dot={false} name="Transactions" />
                  <Line type="monotone" dataKey="fraud_count" stroke="#ef4444" strokeWidth={2} dot={false} name="Fraud" />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Risk Distribution</CardTitle></CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-64 w-full" /> : (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={data?.risk_distribution}
                    dataKey="count"
                    nameKey="level"
                    innerRadius={50}
                    outerRadius={85}
                    paddingAngle={2}
                  >
                    {data?.risk_distribution?.map((entry: any, i: number) => (
                      <Cell key={i} fill={RISK_COLORS[entry.level] || '#64748b'} />
                    ))}
                  </Pie>
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>Fraud by Type</CardTitle></CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-56 w-full" /> : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={data?.fraud_by_type} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(220 15% 18%)" />
                  <XAxis type="number" tick={{ fontSize: 11 }} stroke="hsl(215 12% 60%)" />
                  <YAxis dataKey="type" type="category" width={140} tick={{ fontSize: 11 }} stroke="hsl(215 12% 60%)" />
                  <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', fontSize: 12 }} />
                  <Bar dataKey="count" fill="#38bdf8" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Recent Investigations</CardTitle></CardHeader>
          <CardContent className="space-y-2 max-h-64 overflow-y-auto">
            {isLoading && <Skeleton className="h-56 w-full" />}
            {data?.recent_investigations?.length === 0 && (
              <p className="text-sm text-muted-foreground">No investigations yet. Try the Demo mode.</p>
            )}
            {data?.recent_investigations?.map((inv: any) => (
              <button
                key={inv.id}
                onClick={() => navigate(`/investigation/${inv.transaction_id}`)}
                className="w-full text-left flex items-center justify-between rounded-md border border-border p-2 hover:bg-muted transition-colors"
              >
                <div className="text-xs">
                  <div className="font-mono">{inv.transaction_id}</div>
                  <div className="text-muted-foreground">{inv.recommendation}</div>
                </div>
                <Badge className={cn(riskBadgeClass(inv.risk_level))}>{inv.risk_level}</Badge>
              </button>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, loading, accent }: any) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-4">
        <div>
          <div className="text-xs text-muted-foreground">{label}</div>
          {loading ? <Skeleton className="h-6 w-16 mt-1" /> : (
            <div className={cn('text-xl font-semibold mt-1', accent)}>{value ?? '—'}</div>
          )}
        </div>
        <Icon className={cn('h-8 w-8 opacity-60', accent)} />
      </CardContent>
    </Card>
  );
}
