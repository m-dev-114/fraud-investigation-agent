import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/input';
import { formatCurrency } from '@/lib/utils';
import {
  UserX, Users, Zap, Plane, ShieldCheck, PlayCircle,
} from 'lucide-react';

const ICONS: Record<string, any> = {
  account_takeover: UserX,
  fraud_ring: Users,
  velocity_attack: Zap,
  impossible_travel: Plane,
  none: ShieldCheck,
};

const DESCRIPTIONS: Record<string, string> = {
  account_takeover: 'A dormant device and a foreign IP suddenly drain a customer\'s account within minutes.',
  fraud_ring: 'A cluster of accounts sharing one device and IP cash out through the same merchant.',
  velocity_attack: 'A burst of many transactions from one customer within a single hour.',
  impossible_travel: 'Two transactions from the same customer, thousands of km apart, minutes apart.',
  none: 'A normal, everyday transaction consistent with the customer\'s usual behavior.',
};

export default function Demo() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ['demo-cases'],
    queryFn: api.getDemoCases,
  });

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold">Try Demo Investigation</h1>
        <p className="text-muted-foreground text-sm">
          5 guaranteed cases spanning the fraud patterns in the synthetic dataset. Pick one to run the full
          investigation pipeline against real backend data — ML scoring, evidence correlation, and a risk
          decision.
        </p>
      </div>

      {error && <div className="text-danger text-sm">Failed to load demo cases: {(error as Error).message}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {isLoading && Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-40 w-full" />)}
        {data?.cases?.map((c: any) => {
          const Icon = ICONS[c.fraud_type] || ShieldCheck;
          return (
            <Card key={c.transaction_id} className="flex flex-col">
              <CardContent className="p-5 flex-1 space-y-3">
                <div className="flex items-center gap-2">
                  <Icon className="h-5 w-5 text-primary" />
                  <span className="font-semibold">{c.label}</span>
                </div>
                <p className="text-sm text-muted-foreground">{DESCRIPTIONS[c.fraud_type]}</p>
                <div className="text-xs text-muted-foreground font-mono">
                  {c.transaction_id} · {formatCurrency(c.amount)}
                </div>
              </CardContent>
              <div className="p-4 pt-0">
                <Button className="w-full" onClick={() => navigate(`/investigation/${c.transaction_id}`)}>
                  <PlayCircle className="h-4 w-4" /> Start Investigation
                </Button>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
