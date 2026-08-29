import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/input';
import { formatDate } from '@/lib/utils';
import { ScrollText, User, Cpu, Server } from 'lucide-react';

const ACTOR_ICON: Record<string, any> = { system: Server, agent: Cpu, analyst: User };

function actorIcon(actor: string) {
  const prefix = actor.split(':')[0];
  const Icon = ACTOR_ICON[prefix] || ScrollText;
  return Icon;
}

export default function Audit() {
  const { caseId } = useParams<{ caseId?: string }>();
  const navigate = useNavigate();
  const [input, setInput] = useState(caseId || '');

  const { data, isLoading, error } = useQuery({
    queryKey: ['audit', caseId],
    queryFn: () => api.getAuditTrail(caseId!),
    enabled: !!caseId,
  });

  return (
    <div className="p-6 space-y-4 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold">Audit Trail</h1>
        <p className="text-muted-foreground text-sm">
          Full record of agent actions, tool calls, evidence, and analyst decisions for a case.
        </p>
      </div>

      <Card>
        <CardContent className="p-4 flex gap-2">
          <Input
            placeholder="Enter a case ID (e.g. case_abc123)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && input) navigate(`/audit/${input}`); }}
          />
          <Button onClick={() => input && navigate(`/audit/${input}`)}>Load</Button>
        </CardContent>
      </Card>

      {!caseId && (
        <div className="text-muted-foreground text-sm">
          Enter a case ID above, or open it from an Investigation's "View Audit Trail" link.
        </div>
      )}
      {error && <div className="text-danger text-sm">Failed to load audit trail: {(error as Error).message}</div>}
      {isLoading && <Skeleton className="h-64 w-full" />}

      {data && (
        <Card>
          <CardContent className="p-4 space-y-3">
            {data.length === 0 && <p className="text-sm text-muted-foreground">No audit entries for this case yet.</p>}
            {data.map((log: any) => {
              const Icon = actorIcon(log.actor);
              return (
                <div key={log.id} className="flex gap-3 rounded-md border border-border p-3">
                  <Icon className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium">{log.action.replace(/_/g, ' ')}</span>
                      <Badge className="bg-muted text-muted-foreground">{log.actor}</Badge>
                    </div>
                    <div className="text-[11px] text-muted-foreground mt-0.5">{formatDate(log.created_at)}</div>
                    {log.detail && Object.keys(log.detail).length > 0 && (
                      <pre className="text-[11px] text-muted-foreground mt-2 bg-muted/50 rounded p-2 overflow-x-auto">
                        {JSON.stringify(log.detail, null, 2)}
                      </pre>
                    )}
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
