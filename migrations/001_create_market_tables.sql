-- WP-116: Create market data tables for Massive API + Supabase migration
-- Run this in the Supabase SQL Editor (https://supabase.com/dashboard → SQL Editor)

-- OHLCV price data (stocks + crypto)
CREATE TABLE market_data_daily (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticker           TEXT        NOT NULL,
    asset_type       TEXT        NOT NULL,
    date             DATE        NOT NULL,
    open             NUMERIC     NOT NULL,
    high             NUMERIC     NOT NULL,
    low              NUMERIC     NOT NULL,
    close            NUMERIC     NOT NULL,
    volume           BIGINT      NOT NULL,
    vwap             NUMERIC,
    num_transactions INT,
    ingested_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_market_ticker_date UNIQUE (ticker, date)
);

CREATE INDEX idx_market_ticker_date ON market_data_daily (ticker, date DESC);


-- Technical indicators (EMA, SMA, MACD, RSI, Stochastic)
CREATE TABLE technical_indicators_daily (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticker           TEXT        NOT NULL,
    date             DATE        NOT NULL,
    ema_8            NUMERIC,
    ema_80           NUMERIC,
    sma_200          NUMERIC,
    macd_value       NUMERIC,
    macd_signal      NUMERIC,
    macd_histogram   NUMERIC,
    rsi_14           NUMERIC,
    stoch_k          NUMERIC,
    stoch_d          NUMERIC,
    ingested_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_indicator_ticker_date UNIQUE (ticker, date)
);

CREATE INDEX idx_indicator_ticker_date ON technical_indicators_daily (ticker, date DESC);