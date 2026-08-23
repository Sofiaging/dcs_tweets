CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id UUID PRIMARY KEY,
    requested_start TIMESTAMPTZ NOT NULL,
    requested_end TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    error TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_chunks (
    run_id UUID REFERENCES pipeline_runs(run_id),
    chunk_start TIMESTAMPTZ NOT NULL,
    chunk_end TIMESTAMPTZ NOT NULL,
    raw_key TEXT,
    status TEXT NOT NULL CHECK (status IN ('succeeded', 'failed')),
    record_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, chunk_start, chunk_end)
);

CREATE TABLE IF NOT EXISTS tweets (
    tweet_id TEXT PRIMARY KEY,
    anonymized_user_id TEXT NOT NULL,
    location TEXT,
    follower_count BIGINT,
    tweeted_at TIMESTAMPTZ NOT NULL,
    hashtags TEXT[] NOT NULL DEFAULT '{}',
    tweet_count BIGINT,
    is_retweet BOOLEAN NOT NULL DEFAULT false,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_chunks_status_start
    ON pipeline_chunks (status, chunk_start);

CREATE INDEX IF NOT EXISTS idx_tweets_tweeted_at
    ON tweets (tweeted_at);

CREATE INDEX IF NOT EXISTS idx_tweets_anonymized_user_id
    ON tweets (anonymized_user_id);
