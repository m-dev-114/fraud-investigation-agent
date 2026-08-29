import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/input';
import { cn } from '@/lib/utils';

function MetricsBlock({ title, metrics }: { title: string; metrics: any }) {
  if (!metrics) {
    return (
      <Card>
        <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Model metrics not available. Run <code>scripts/train_model.py</code> to generate them.
        </CardContent>
      </Card>
    );
  }
  const cm = metrics.confusion_matrix;
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <Metric label="Precision" value={metrics.precision} />
          <Metric label="Recall" value={metrics.recall} />
          <Metric label="F1" value={metrics.f1} />
          <Metric label="ROC-AUC" value={metrics.roc_auc} />
          <Metric label="PR-AUC" value={metrics.pr_auc} />
        </div>

        <div>
          <div className="text-xs text-muted-foreground mb-2">
            Confusion Matrix (test set n={metrics.n_test?.toLocaleString()}, trained on n={metrics.n_train?.toLocaleString()})
          </div>
          <div className="grid grid-cols-2 gap-1 max-w-xs text-center text-sm">
            <div className="bg-success/10 text-success rounded p-3">
              <div className="text-lg font-semibold">{cm.true_negative}</div>
              <div className="text-[10px]">True Negative</div>
            </div>
            <div className="bg-warning/10 text-warning rounded p-3">
              <div className="text-lg font-semibold">{cm.false_positive}</div>
              <div className="text-[10px]">False Positive</div>
            </div>
            <div className="bg-warning/10 text-warning rounded p-3">
              <div className="text-lg font-semibold">{cm.false_negative}</div>
              <div className="text-[10px]">False Negative</div>
            </div>
            <div className="bg-success/10 text-success rounded p-3">
              <div className="text-lg font-semibold">{cm.true_positive}</div>
              <div className="text-[10px]">True Positive</div>
            </div>
          </div>
        </div>

        {metrics.feature_importance?.length > 0 && (
          <div>
            <div className="text-xs text-muted-foreground mb-2">Top Features</div>
            <div className="space-y-1">
              {metrics.feature_importance.slice(0, 8).map((f: any) => (
                <div key={f.feature} className="flex items-center gap-2 text-xs">
                  <span className="w-48 truncate text-muted-foreground">{f.feature}</span>
                  <div className="flex-1 bg-muted rounded h-2 overflow-hidden">
                    <div
                      className="h-full bg-primary"
                      style={{ width: `${Math.min(Math.abs(f.importance) * 100, 100)}%` }}
                    />
                  </div>
                  <span className="w-14 text-right">{f.importance.toFixed(3)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border p-3 text-center">
      <div className="text-xl font-semibold">{(value * 100).toFixed(1)}%</div>
      <div className="text-[10px] text-muted-foreground uppercase tracking-wide mt-1">{label}</div>
    </div>
  );
}

export default function ModelPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['model-metrics'],
    queryFn: api.getModelMetrics,
  });

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold">Model Performance</h1>
        <p className="text-muted-foreground text-sm">
          Actual metrics computed on a held-out, time-based test split. No fabricated numbers.
        </p>
      </div>

      {error && <div className="text-danger text-sm">Failed to load metrics: {(error as Error).message}</div>}
      {isLoading && <Skeleton className="h-96 w-full" />}

      {data && (
        <div className="space-y-6">
          <MetricsBlock title="XGBoost (Primary Model)" metrics={data.xgboost} />
          <MetricsBlock title="Logistic Regression (Baseline)" metrics={data.logistic_regression} />
        </div>
      )}
    </div>
  );
}
