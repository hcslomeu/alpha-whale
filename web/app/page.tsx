"use client";

import { useState, useEffect, useRef } from "react";
import { PillNav } from "@/components/pill-nav";
import { ChatPanel, type StudyConfig } from "@/components/chat-panel";
import { TradingViewChart } from "@/components/tradingview-chart";
import { Spinner } from "@/components/ui/spinner";

// Oscillators render in a sub-pane — only one active at a time.
// Overlays (EMA, SMA) render on the price series and may stack.
const OSCILLATOR_IDS = new Set(["STD;RSI", "STD;MACD", "STD;Stochastic"]);

function isOscillator(study: StudyConfig): boolean {
  return typeof study === "string" && OSCILLATOR_IDS.has(study);
}

function studyKey(study: StudyConfig): string {
  return JSON.stringify(study);
}

export default function Home() {
  const [mounted, setMounted] = useState(false);
  const [symbol, setSymbol] = useState("NASDAQ:NVDA");
  const [studies, setStudies] = useState<StudyConfig[]>(["STD;Stochastic"]);
  const [isChartChanging, setIsChartChanging] = useState(false);
  const chartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Tracks the last symbol we actually applied — prevents the agent's confirmation
  // message (which mentions the same ticker) from re-triggering the overlay.
  const activeSymbolRef = useRef("NASDAQ:NVDA");

  useEffect(() => {
    setMounted(true);
    return () => {
      if (chartTimerRef.current) clearTimeout(chartTimerRef.current);
    };
  }, []);

  const handleSymbolChange = (newSymbol: string) => {
    if (newSymbol === activeSymbolRef.current) return;
    activeSymbolRef.current = newSymbol;
    setSymbol(newSymbol);
    setIsChartChanging(true);
    if (chartTimerRef.current) clearTimeout(chartTimerRef.current);
    chartTimerRef.current = setTimeout(() => setIsChartChanging(false), 1400);
  };

  const handleStudyToggle = (action: "add" | "remove", studyConfig: StudyConfig) => {
    if (action === "remove") {
      setStudies((prev) =>
        prev.filter((s) => {
          // A generic string ID (e.g. "STD;EMA") should also remove period-specific
          // object configs with the same base ID (e.g. { id: "STD;EMA", inputs: {...} })
          if (typeof studyConfig === "string") {
            return typeof s === "string" ? s !== studyConfig : s.id !== studyConfig;
          }
          return studyKey(s) !== studyKey(studyConfig);
        }),
      );
      return;
    }
    if (isOscillator(studyConfig)) {
      // Sub-pane indicators: replace any existing oscillator, keep all overlays
      setStudies((prev) => [...prev.filter((s) => !isOscillator(s)), studyConfig]);
    } else {
      // Overlays: append unless already present (exact config match)
      setStudies((prev) =>
        prev.some((s) => studyKey(s) === studyKey(studyConfig))
          ? prev
          : [...prev, studyConfig],
      );
    }
  };

  if (!mounted) return null;

  return (
    <div className="h-screen w-full">
      <PillNav />

      <section className="h-screen w-full pt-24 pb-8 px-4 flex flex-col overflow-hidden">
        <div className="flex-1 flex flex-col h-full max-w-7xl mx-auto w-full gap-4">
          <div className="h-[60%] relative w-full rounded-2xl border bg-card overflow-hidden shadow-sm">
            <TradingViewChart symbol={symbol} studies={studies} />
            {isChartChanging && (
              <div
                className="absolute inset-0 flex items-center justify-center pointer-events-none"
                style={{ backgroundColor: "rgba(26, 34, 46, 0.88)" }}
              >
                <div className="flex items-center gap-2">
                  <Spinner className="size-5 text-primary" />
                  <span className="text-sm text-muted-foreground">Loading chart...</span>
                </div>
              </div>
            )}
          </div>

          <div className="h-[40%] flex flex-col overflow-hidden">
            <ChatPanel onSymbolChange={handleSymbolChange} onStudyToggle={handleStudyToggle} />
          </div>
        </div>
      </section>
    </div>
  );
}
