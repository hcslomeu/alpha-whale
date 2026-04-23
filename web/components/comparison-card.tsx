import { ArrowLeftRight } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

interface ComparisonCardProps {
  metric: string;
  tickers: string[];
  data: Record<string, { date: string; value: number }[]>;
  summary: string;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatValue(value: number, metric: string): string {
  if (metric === "volume") {
    return value >= 1_000_000
      ? `${(value / 1_000_000).toFixed(1)}M`
      : value.toLocaleString();
  }
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

export function ComparisonCard({
  metric,
  tickers,
  data,
  summary,
}: ComparisonCardProps) {
  if (tickers.length === 0) return null;

  const rows = (data[tickers[0]] ?? []).slice(0, 5);
  const dates = rows.map((d) => d.date);

  return (
    <div className="w-fit rounded-lg border border-primary/10 bg-card/60 backdrop-blur-sm overflow-hidden">
      <div className="flex items-center gap-2 px-2.5 py-1.5 border-b border-primary/10">
        <ArrowLeftRight className="h-3 w-3 text-primary" />
        <span className="text-[11px] font-bold tracking-wide">
          {tickers.join(" vs ")}{" "}
          <span className="font-normal text-muted-foreground capitalize">
            ({metric})
          </span>
        </span>
      </div>
      <div className="px-1.5 pb-1.5">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent border-primary/10">
              <TableHead className="text-[11px] text-muted-foreground">
                Date
              </TableHead>
              {tickers.map((t) => (
                <TableHead
                  key={t}
                  className="text-[11px] text-muted-foreground text-right"
                >
                  {t}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {dates.map((date, i) => (
              <TableRow
                key={date}
                className="hover:bg-muted/30 border-primary/5"
              >
                <TableCell className="text-[11px] font-medium">
                  {formatDate(date)}
                </TableCell>
                {tickers.map((t) => {
                  const entries = data[t];
                  const current = entries?.[i]?.value;
                  const previous = entries?.[i + 1]?.value;
                  if (current == null) return <TableCell key={t} className="text-[11px] text-right font-mono">—</TableCell>;

                  const hasPrev = previous != null && previous !== 0;
                  const pct = hasPrev ? ((current - previous) / previous) * 100 : null;
                  const isUp = pct != null && pct >= 0;

                  return (
                    <TableCell
                      key={t}
                      className="text-[11px] text-right font-mono"
                    >
                      {formatValue(current, metric)}
                      {pct != null && (
                        <>
                          {" "}
                          <span className={cn(isUp ? "text-emerald-500" : "text-red-500")}>
                            ({isUp ? "+" : ""}{pct.toFixed(2)}%)
                          </span>
                        </>
                      )}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {summary && (
          <p className="mt-1 text-[11px] text-muted-foreground italic border-t border-primary/5 pt-1">
            {summary}
          </p>
        )}
      </div>
    </div>
  );
}
