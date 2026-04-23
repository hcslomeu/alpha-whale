"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowLeftRight,
  BitcoinCircle,
  ChartLine,
  Dollar,
  TrendingUp,
  ChartCandlestick,
} from "@mynaui/icons-react";
import {
  Send,
  Square,
  User,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { StockDataCard } from "@/components/stock-data-card";
import { IndicatorsCard } from "@/components/indicators-card";
import { ComparisonCard } from "@/components/comparison-card";
import { streamChat } from "@/lib/sse-client";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const WELCOME_MESSAGE: Message = {
  role: "assistant",
  content: "Hello! The market is open. What would you like to know about today?",
};

// Company name → ticker (checked before raw ticker symbols)
const COMPANY_NAME_MAP: Record<string, string> = {
  APPLE: "AAPL",
  MICROSOFT: "MSFT",
  GOOGLE: "GOOGL",
  ALPHABET: "GOOGL",
  AMAZON: "AMZN",
  NVIDIA: "NVDA",
  FACEBOOK: "META",
  TESLA: "TSLA",
  BITCOIN: "BTC",
  ETHEREUM: "ETH",
  SOLANA: "SOL",
};

const STOCK_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"];
const CRYPTO_TICKER_MAP: Record<string, string> = {
  BTC: "COINBASE:BTCUSD",
  ETH: "COINBASE:ETHUSD",
  SOL: "COINBASE:SOLUSD",
};

// "add RSI", "show RSI", "show me the MACD"
// Indicator group captures EMA/SMA with optional period: "EMA 8", "ema80", "SMA 200"
const IND = "(rsi|macd|stochastic|ema(?:\\s*\\d+)?|sma(?:\\s*\\d+)?)";

const STUDY_ADD_PATTERN = new RegExp(
  `\\b(?:add|show|enable|put|display)\\s+(?:(?:me|us)\\s+)?(?:the\\s+)?${IND}\\b`,
  "i",
);
// "RSI added to the chart" — passive confirmation from agent
const STUDY_ADDED_PATTERN = new RegExp(
  `\\b${IND}\\b.{0,25}\\badded\\b`,
  "i",
);
// "change/switch/replace … to/with RSI" — no `s` flag needed (single-line messages)
const STUDY_SWITCH_PATTERN = new RegExp(
  `\\b(?:change|switch|replac)\\w*\\b.{0,60}\\b(?:to|with)\\s+(?:the\\s+)?${IND}\\b`,
  "i",
);
const STUDY_REMOVE_PATTERN = new RegExp(
  `\\b(?:remove|hide|disable|take off|clear)\\s+(?:the\\s+)?${IND}\\b`,
  "i",
);

export type StudyConfig = string | { id: string; inputs: Record<string, number> };

// Normalize "EMA8" / "EMA 8" / "ema  8" → "ema 8" for consistent map lookup
function normalizeIndicator(raw: string): string {
  return raw.toLowerCase().trim().replace(/\s+/g, " ").replace(/([a-z])(\d)/, "$1 $2");
}

function indicatorToStudyConfig(raw: string): StudyConfig | null {
  const normalized = normalizeIndicator(raw);
  if (normalized === "rsi") return "STD;RSI";
  if (normalized === "macd") return "STD;MACD";
  if (normalized === "stochastic") return "STD;Stochastic";

  const maMatch = normalized.match(/^(ema|sma)(?: (\d+))?$/);
  if (!maMatch) return null;

  const [, kind, length] = maMatch;
  const id = kind === "ema" ? "STD;EMA" : "STD;SMA";
  return length ? { id, inputs: { length: Number(length) } } : id;
}

function resolveToTradingViewSymbol(ticker: string): string {
  return CRYPTO_TICKER_MAP[ticker] ?? `NASDAQ:${ticker}`;
}

function extractSymbol(text: string): string | null {
  const upper = text.toUpperCase();

  // Company names take priority (e.g. "Apple" before ticker "AAPL")
  for (const [name, ticker] of Object.entries(COMPANY_NAME_MAP)) {
    if (new RegExp(`\\b${name}\\b`).test(upper)) {
      return resolveToTradingViewSymbol(ticker);
    }
  }

  // Raw crypto tickers
  for (const [ticker, symbol] of Object.entries(CRYPTO_TICKER_MAP)) {
    if (new RegExp(`\\b${ticker}\\b`).test(upper)) return symbol;
  }

  // Raw stock tickers
  for (const ticker of STOCK_TICKERS) {
    if (new RegExp(`\\b${ticker}\\b`).test(upper)) return `NASDAQ:${ticker}`;
  }

  return null;
}

function extractStudyCommand(text: string): { action: "add" | "remove"; studyConfig: StudyConfig } | null {
  // Check remove first — most explicit intent
  const removeMatch = text.match(STUDY_REMOVE_PATTERN);
  if (removeMatch) {
    const studyConfig = indicatorToStudyConfig(removeMatch[1]);
    return studyConfig ? { action: "remove", studyConfig } : null;
  }

  // Check add patterns in order of specificity; all capture the indicator in group 1
  const addMatch =
    text.match(STUDY_ADD_PATTERN) ??
    text.match(STUDY_ADDED_PATTERN) ??
    text.match(STUDY_SWITCH_PATTERN);
  if (addMatch) {
    const studyConfig = indicatorToStudyConfig(addMatch[1] ?? "");
    return studyConfig ? { action: "add", studyConfig } : null;
  }

  return null;
}

const FINANCIAL_DATA_REGEX = /```financial-data\r?\n([\s\S]*?)\r?\n```/;

function hasRequiredFields(data: unknown): boolean {
  return typeof data === "object" && data !== null && "type" in data && "data" in data;
}

function renderMessageContent(content: string, isStreaming: boolean) {
  if (isStreaming) return <>{content}</>;

  const match = content.match(FINANCIAL_DATA_REGEX);
  if (!match) return <>{content}</>;

  try {
    const raw = JSON.parse(match[1]);
    if (!hasRequiredFields(raw)) return <>{content}</>;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- validated above, catch handles malformed data
    const parsed = raw as any;
    return (
      <>
        {parsed.type === "stock" && (
          <StockDataCard
            ticker={String(parsed.ticker ?? "")}
            data={Array.isArray(parsed.data) ? parsed.data : []}
            summary={String(parsed.summary ?? "")}
          />
        )}
        {parsed.type === "indicators" && (
          <IndicatorsCard
            ticker={String(parsed.ticker ?? "")}
            data={Array.isArray(parsed.data) ? parsed.data : []}
            summary={String(parsed.summary ?? "")}
          />
        )}
        {parsed.type === "comparison" && (
          <ComparisonCard
            metric={String(parsed.metric ?? "close")}
            tickers={Array.isArray(parsed.tickers) ? parsed.tickers : []}
            data={parsed.data ?? {}}
            summary={String(parsed.summary ?? "")}
          />
        )}
      </>
    );
  } catch {
    return <>{content}</>;
  }
}

const SUGGESTION_CHIPS = [
  { icon: ChartCandlestick, label: "Get stock price", prompt: "How is NVDA performing this week?" },
  { icon: ArrowLeftRight, label: "Compare assets", prompt: "Compare AAPL vs MSFT over the last 7 days" },
  { icon: ChartLine, label: "Add indicator", prompt: "Add RSI to the chart" },
  { icon: BitcoinCircle, label: "Crypto check", prompt: "How is Bitcoin doing today?" },
] as const;

interface ChatPanelProps {
  onSymbolChange?: (symbol: string) => void;
  onStudyToggle?: (action: "add" | "remove", studyConfig: StudyConfig) => void;
}

const THINKING_PHRASES = [
  "Thinking...",
  "Investigating...",
  "Gathering data...",
  "Analyzing...",
  "Crunching numbers...",
];

export function ChatPanel({ onSymbolChange, onStudyToggle }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinkingIndex, setThinkingIndex] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const scrollBottomRef = useRef<HTMLDivElement>(null);
  const streamingContentRef = useRef("");

  useEffect(() => {
    scrollBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const isThinkingPhase =
    isStreaming &&
    messages.length > 0 &&
    messages[messages.length - 1].role === "assistant" &&
    messages[messages.length - 1].content === "";

  useEffect(() => {
    if (!isThinkingPhase) {
      setThinkingIndex(0);
      return;
    }
    const id = setInterval(() => {
      setThinkingIndex((prev) => (prev + 1) % THINKING_PHRASES.length);
    }, 2000);
    return () => clearInterval(id);
  }, [isThinkingPhase]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;

    const detected = extractSymbol(trimmed);
    if (detected && onSymbolChange) {
      onSymbolChange(detected);
    }

    const studyCmd = extractStudyCommand(trimmed);
    if (studyCmd && onStudyToggle) {
      onStudyToggle(studyCmd.action, studyCmd.studyConfig);
    }

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setIsStreaming(true);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
    streamingContentRef.current = "";

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(
        trimmed,
        {
          onToken: (token) => {
            streamingContentRef.current += token;
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: updated[updated.length - 1].content + token,
              };
              return updated;
            });
          },
          onError: (error) => {
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: `Error: ${error}`,
              };
              return updated;
            });
          },
          onDone: () => {
            // Only parse agent response for chart commands when it contains an
            // explicit chart-confirmation phrase — avoids jumping the chart on
            // incidental ticker mentions in data answers (e.g. "NVDA's RSI is 62").
            const responseText = streamingContentRef.current;
            const isChartConfirmation = /\bhere is\b|\bchart\b/i.test(responseText);
            if (isChartConfirmation) {
              const responseSymbol = extractSymbol(responseText);
              if (responseSymbol && onSymbolChange) onSymbolChange(responseSymbol);
            }
            const responseStudy = extractStudyCommand(responseText);
            if (responseStudy && onStudyToggle) onStudyToggle(responseStudy.action, responseStudy.studyConfig);
            setIsStreaming(false);
            abortRef.current = null;
          },
        },
        controller.signal,
      );
    } catch (err) {
      const wasAborted =
        err instanceof Error && err.name === "AbortError";

      if (!wasAborted) {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant" && last.content === "") {
            updated[updated.length - 1] = {
              ...last,
              content:
                "Connection error — is the backend running? Start it with: poetry run uvicorn api.main:app",
            };
          }
          return updated;
        });
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  };

  const isInitialState =
    messages.length === 1 &&
    messages[0]?.role === "assistant" &&
    messages[0]?.content === WELCOME_MESSAGE.content;

  const handleChipClick = (prompt: string) => {
    setInput(prompt);
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setIsStreaming(false);
    abortRef.current = null;
  };

  return (
    <div className="max-w-3xl mx-auto w-full flex flex-col h-full pb-4 min-h-0">
      {/* min-h-0 on both the flex container and this div are required for
          overflow-y-auto to activate — flex children default to min-height: auto
          which prevents them from shrinking below their content height */}
      <div className="flex-1 overflow-y-auto min-h-0 px-4 mb-4 scrollbar-hidden">
        <div className="flex flex-col gap-4 py-4">
          {messages.map((message, index) => {
            const isUser = message.role === "user";
            const isLastAssistant = !isUser && index === messages.length - 1 && isStreaming;
            const isThinking = isLastAssistant && message.content === "";
            const isTyping = isLastAssistant && message.content !== "";

            return (
              <div
                key={index}
                className={cn(
                  "flex items-end gap-2",
                  isUser ? "flex-row-reverse" : "flex-row",
                )}
              >
                <Avatar className={cn("h-8 w-8 shrink-0", !isUser && "bg-primary")}>
                  {isUser ? (
                    <AvatarFallback>
                      <User className="h-4 w-4" />
                    </AvatarFallback>
                  ) : (
                    <>
                      <AvatarImage
                        src="/logan_logo.svg"
                        alt="AlphaWhale"
                        className="object-contain p-1"
                      />
                      <AvatarFallback className="bg-primary text-primary-foreground text-xs">
                        AW
                      </AvatarFallback>
                    </>
                  )}
                </Avatar>
                <div
                  className={cn(
                    "rounded-2xl px-4 py-2 text-sm max-w-[80%]",
                    isUser
                      ? "bg-foreground text-background"
                      : "bg-card border",
                  )}
                >
                  {isThinking ? (
                    <span className="flex gap-1.5 items-center py-0.5 w-40">
                      <Spinner className="size-4 text-muted-foreground shrink-0" />
                      <span key={thinkingIndex} className="text-xs text-muted-foreground animate-fade-in">
                        {THINKING_PHRASES[thinkingIndex]}
                      </span>
                    </span>
                  ) : (
                    <>
                      {renderMessageContent(message.content, isTyping)}
                      {isTyping && (
                        <span className="inline-block w-1.5 h-4 bg-foreground/50 ml-0.5 animate-pulse" />
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={scrollBottomRef} />
        </div>
      </div>

      <div className="px-4">
        <div className="relative">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void handleSend();
              }
            }}
            disabled={isStreaming}
            placeholder="e.g. How is NVDA performing this week?"
            className="rounded-full bg-card/80 backdrop-blur-sm border h-12 pl-6 pr-14 shadow-sm focus-visible:ring-primary"
          />
          {isStreaming ? (
            <Button
              aria-label="Stop streaming"
              onClick={handleStop}
              variant="destructive"
              size="icon"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full h-8 w-8"
            >
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              aria-label="Send message"
              onClick={() => void handleSend()}
              size="icon"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full h-8 w-8"
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>

        {isInitialState && (
          <div className="flex justify-center gap-2 mt-2 flex-wrap pb-1">
            {SUGGESTION_CHIPS.map((chip) => (
              <Button
                key={chip.label}
                variant="outline"
                size="sm"
                onClick={() => handleChipClick(chip.prompt)}
                className="rounded-full bg-card text-muted-foreground hover:text-foreground shadow-sm"
              >
                <chip.icon />
                {chip.label}
              </Button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
