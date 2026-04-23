import { TrendingDown, TrendingUp } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

interface StockRow {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
}

interface StockDataCardProps {
  ticker: string;
  data: StockRow[];
  summary: string;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatPrice(value: number): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

export function StockDataCard({ ticker, data, summary }: StockDataCardProps) {
  if (data.length === 0) return null;

  const rows = data.slice(0, 5);
  const latest = rows[0];
  const oldest = rows[rows.length - 1];
  const periodChange = latest.close - oldest.open;
  const periodPct = oldest.open !== 0 ? (periodChange / oldest.open) * 100 : 0;
  const isPositive = periodChange >= 0;

  return (
    <div className="w-fit rounded-lg border border-primary/10 bg-card/60 backdrop-blur-sm overflow-hidden">
      <div className="flex items-center gap-2 px-2.5 py-1.5 border-b border-primary/10">
        <span className="text-[11px] font-bold tracking-wide">{ticker}</span>
        <span
          className={cn(
            "inline-flex items-center gap-1 font-mono text-[11px]",
            isPositive ? "text-emerald-500" : "text-red-500",
          )}
        >
          {isPositive ? (
            <TrendingUp className="h-3 w-3" />
          ) : (
            <TrendingDown className="h-3 w-3" />
          )}
          {isPositive ? "+" : ""}
          {periodChange.toFixed(2)} ({periodPct.toFixed(2)}%)
        </span>
      </div>
      <div className="px-1.5 pb-1.5">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent border-primary/10">
              <TableHead className="text-[11px] text-muted-foreground">
                Date
              </TableHead>
              <TableHead className="text-[11px] text-muted-foreground text-right">
                Close
              </TableHead>
              <TableHead className="text-[11px] text-muted-foreground text-right">
                Change
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => {
              const dailyChange = row.close - row.open;
              const dailyPct = row.open !== 0 ? (dailyChange / row.open) * 100 : 0;
              const dailyUp = dailyChange >= 0;
              return (
                <TableRow
                  key={row.date}
                  className="hover:bg-muted/30 border-primary/5"
                >
                  <TableCell className="text-[11px] font-medium">
                    {formatDate(row.date)}
                  </TableCell>
                  <TableCell className="text-[11px] text-right font-mono">
                    {formatPrice(row.close)}
                  </TableCell>
                  <TableCell
                    className={cn(
                      "text-[11px] text-right font-mono",
                      dailyUp ? "text-emerald-500" : "text-red-500",
                    )}
                  >
                    {dailyUp ? "+" : ""}
                    {dailyChange.toFixed(2)} ({dailyPct.toFixed(2)}%)
                  </TableCell>
                </TableRow>
              );
            })}
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
