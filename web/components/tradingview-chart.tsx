"use client";

import { useEffect, useRef } from "react";
import type { StudyConfig } from "@/components/chat-panel";

interface TradingViewChartProps {
  symbol?: string;
  interval?: string;
  studies?: StudyConfig[];
}

export function TradingViewChart({
  symbol = "NASDAQ:NVDA",
  interval = "D",
  studies = ["STD;Stochastic"],
}: TradingViewChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }

    const widgetDiv = document.createElement("div");
    widgetDiv.className = "tradingview-widget-container__widget";
    widgetDiv.style.height = "100%";
    widgetDiv.style.width = "100%";
    container.appendChild(widgetDiv);

    const script = document.createElement("script");
    script.type = "text/javascript";
    script.src =
      "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.async = true;
    script.textContent = JSON.stringify({
      symbol,
      interval,
      timezone: "Etc/UTC",
      theme: "dark",
      style: "1",
      locale: "en",
      backgroundColor: "rgba(26, 34, 46, 1)",
      gridColor: "rgba(35, 45, 59, 1)",
      hide_top_toolbar: false,
      hide_side_toolbar: false,
      hide_volume: true,
      allow_symbol_change: true,
      save_image: false,
      calendar: false,
      support_host: "https://www.tradingview.com",
      studies,
      width: "100%",
      height: "100%",
    });

    container.appendChild(script);

    return () => {
      while (container.firstChild) {
        container.removeChild(container.firstChild);
      }
    };
  }, [symbol, interval, studies]);

  return (
    <div
      ref={containerRef}
      className="tradingview-widget-container w-full h-full"
    />
  );
}
