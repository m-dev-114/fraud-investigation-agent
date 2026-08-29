import { useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import ReactFlow, {
  Background, Controls, MiniMap, type Node, type Edge, MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { api } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/input';

const TYPE_COLOR: Record<string, string> = {
  customer: '#38bdf8', device: '#a78bfa', ip: '#fb923c', merchant: '#34d399', transaction: '#f472b6',
};
const RISK_BORDER: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e',
};

function layout(nodes: any[], edges: any[]): { rfNodes: Node[]; rfEdges: Edge[] } {
  // simple layered layout by type, since we don't have dagre available
  const order = ['customer', 'device', 'ip', 'transaction', 'merchant'];
  const byType: Record<string, any[]> = {};
  nodes.forEach((n) => {
    byType[n.type] = byType[n.type] || [];
    byType[n.type].push(n);
  });

  const rfNodes: Node[] = [];
  order.forEach((type, colIdx) => {
    (byType[type] || []).forEach((n, rowIdx) => {
      rfNodes.push({
        id: n.id,
        position: { x: colIdx * 260, y: rowIdx * 110 },
        data: { label: n.label, type: n.type, risk: n.risk },
        style: {
          background: '#111827',
          color: '#e5e7eb',
          border: `2px solid ${n.risk ? RISK_BORDER[n.risk] || '#374151' : TYPE_COLOR[n.type] || '#374151'}`,
          borderRadius: 10,
          padding: 8,
          fontSize: 11,
          width: 180,
        },
      });
    });
  });

  const rfEdges: Edge[] = edges.map((e: any) => ({
    id: e.id, source: e.source, target: e.target, label: e.label,
    style: { stroke: '#374151' }, labelStyle: { fill: '#9ca3af', fontSize: 10 },
    markerEnd: { type: MarkerType.ArrowClosed, color: '#374151' },
  }));

  return { rfNodes, rfEdges };
}

export default function FraudNetwork() {
  const { transactionId } = useParams<{ transactionId?: string }>();
  const navigate = useNavigate();
  const [input, setInput] = useState(transactionId || '');

  const { data, isLoading, error } = useQuery({
    queryKey: ['network', transactionId],
    queryFn: () => api.getNetwork(transactionId!),
    enabled: !!transactionId,
  });

  const { rfNodes, rfEdges } = useMemo(
    () => (data ? layout(data.nodes, data.edges) : { rfNodes: [], rfEdges: [] }),
    [data]
  );

  return (
    <div className="p-6 space-y-4 h-full flex flex-col">
      <div>
        <h1 className="text-2xl font-semibold">Fraud Network</h1>
        <p className="text-muted-foreground text-sm">
          Customer → Device → IP → Merchant → Transaction graph, expanded to surface shared devices/IPs across
          accounts.
        </p>
      </div>

      <Card>
        <CardContent className="p-4 flex gap-2">
          <Input
            placeholder="Enter a transaction ID (e.g. txn_0000123)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && input) navigate(`/network/${input}`); }}
          />
          <Button onClick={() => input && navigate(`/network/${input}`)}>Load</Button>
        </CardContent>
      </Card>

      {!transactionId && (
        <div className="text-muted-foreground text-sm">
          Enter a transaction ID above, or open a transaction from the Investigation page and click
          "Fraud Network".
        </div>
      )}
      {error && <div className="text-danger text-sm">Failed to load network: {(error as Error).message}</div>}
      {isLoading && <Skeleton className="h-[500px] w-full" />}

      {data && (
        <Card className="flex-1 min-h-[550px]">
          <div style={{ height: 550 }}>
            <ReactFlow
              nodes={rfNodes}
              edges={rfEdges}
              fitView
              nodesDraggable
              nodesConnectable={false}
              elementsSelectable
            >
              <Background color="#1f2937" gap={20} />
              <Controls />
              <MiniMap
                nodeColor={(n) => (n.data?.risk ? RISK_BORDER[n.data.risk] : TYPE_COLOR[n.data?.type]) || '#374151'}
                maskColor="rgba(0,0,0,0.6)"
              />
            </ReactFlow>
          </div>
        </Card>
      )}

      {data && (
        <div className="flex gap-4 text-xs text-muted-foreground flex-wrap">
          {Object.entries(TYPE_COLOR).map(([type, color]) => (
            <div key={type} className="flex items-center gap-1.5 capitalize">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} /> {type}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
