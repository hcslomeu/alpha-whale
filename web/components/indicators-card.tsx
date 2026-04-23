import { Activity } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

interface IndicatorRow {
  date: string;
  ema_8?: number;
  ema_80?: number;
  sma_200?: number;
  rsi_14?: number;
  macd_value?: number;
  macd_signal?: number;
  stoch_k?: number;
  stoch_d?: number;
}

interface IndicatorsCardProps {
  ticker: string;
  data: IndicatorRow[];
  summary: string;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function rsiColor(value: number): string {
  if (value >= 70) return "text-red-500";
  if (value <= 30) return "text-emerald-500";
  return "text-foreground";
}

function stochColor(value: number): string {
  if (value >= 80) return "text-red-500";
  if (value <= 20) return "text-emerald-500";
  return "text-foreground";
}

export function IndicatorsCard({ ticker, data, summary }: IndicatorsCardProps) {
  if (data.length === 0) return null;

  const latest = data[0];
  const hasMovingAvgs =
    latest.ema_8 !== undefined ||
    latest.ema_80 !== undefined ||
    latest.sma_200 !== undefined;
  const hasMomentum =
    latest.rsi_14 !== undefined ||
    latest.macd_value !== undefined ||
    latest.stoch_k !== undefined;

  return (
    <Card className="w-full bg-card/60 backdrop-blur-sm border-primary/10 overflow-hidden">
      <CardHeader className="flex flex-row items-center gap-2 space-y-0 pb-1.5 pt-2.5 px-3">
        <Activity className="h-3.5 w-3.5 text-primary" />
        <CardTitle className="text-xs font-bold tracking-wide">
          {ticker} Technical Indicators
        </CardTitle>
      </CardHeader>
      <CardContent className="px-3 pb-2.5 pt-0 space-y-2">
        {hasMovingAvgs && (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent border-primary/10">
                <TableHead className="text-[11px] text-muted-foreground">
                  Date
                </TableHead>
                {latest.ema_8 !== undefined && (
                  <TableHead className="text-[11px] text-muted-foreground text-right">
                    EMA 8
                  </TableHead>
                )}
                {latest.ema_80 !== undefined && (
                  <TableHead className="text-[11px] text-muted-foreground text-right">
                    EMA 80
                  </TableHead>
                )}
                {latest.sma_200 !== undefined && (
                  <TableHead className="text-[11px] text-muted-foreground text-right">
                    SMA 200
                  </TableHead>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((row) => (
                <TableRow
                  key={row.date}
                  className="hover:bg-muted/30 border-primary/5"
                >
                  <TableCell className="text-[11px] font-medium">
                    {formatDate(row.date)}
                  </TableCell>
                  {row.ema_8 !== undefined && (
                    <TableCell className="text-[11px] text-right font-mono">
                      {row.ema_8.toFixed(2)}
                    </TableCell>
                  )}
                  {row.ema_80 !== undefined && (
                    <TableCell className="text-[11px] text-right font-mono">
                      {row.ema_80.toFixed(2)}
                    </TableCell>
                  )}
                  {row.sma_200 !== undefined && (
                    <TableCell className="text-[11px] text-right font-mono">
                      {row.sma_200.toFixed(2)}
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {hasMomentum && (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent border-primary/10">
                <TableHead className="text-[11px] text-muted-foreground">
                  Date
                </TableHead>
                {latest.rsi_14 !== undefined && (
                  <TableHead className="text-[11px] text-muted-foreground text-right">
                    RSI
                  </TableHead>
                )}
                {latest.macd_value !== undefined && (
                  <TableHead className="text-[11px] text-muted-foreground text-right">
                    MACD
                  </TableHead>
                )}
                {latest.macd_signal !== undefined && (
                  <TableHead className="text-[11px] text-muted-foreground text-right">
                    Signal
                  </TableHead>
                )}
                {latest.stoch_k !== undefined && (
                  <TableHead className="text-[11px] text-muted-foreground text-right">
                    Stoch K
                  </TableHead>
                )}
                {latest.stoch_d !== undefined && (
                  <TableHead className="text-[11px] text-muted-foreground text-right">
                    Stoch D
                  </TableHead>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((row) => (
                <TableRow
                  key={row.date}
                  className="hover:bg-muted/30 border-primary/5"
                >
                  <TableCell className="text-[11px] font-medium">
                    {formatDate(row.date)}
                  </TableCell>
                  {row.rsi_14 !== undefined && (
                    <TableCell
                      className={cn(
                        "text-[11px] text-right font-mono",
                        rsiColor(row.rsi_14),
                      )}
                    >
                      {row.rsi_14.toFixed(1)}
                    </TableCell>
                  )}
                  {row.macd_value !== undefined && (
                    <TableCell className="text-[11px] text-right font-mono">
                      {row.macd_value.toFixed(2)}
                    </TableCell>
                  )}
                  {row.macd_signal !== undefined && (
                    <TableCell className="text-[11px] text-right font-mono">
                      {row.macd_signal.toFixed(2)}
                    </TableCell>
                  )}
                  {row.stoch_k !== undefined && (
                    <TableCell
                      className={cn(
                        "text-[11px] text-right font-mono",
                        stochColor(row.stoch_k),
                      )}
                    >
                      {row.stoch_k.toFixed(1)}
                    </TableCell>
                  )}
                  {row.stoch_d !== undefined && (
                    <TableCell
                      className={cn(
                        "text-[11px] text-right font-mono",
                        stochColor(row.stoch_d),
                      )}
                    >
                      {row.stoch_d.toFixed(1)}
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {summary && (
          <p className="text-[11px] text-muted-foreground italic border-t border-primary/5 pt-1.5">
            {summary}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
