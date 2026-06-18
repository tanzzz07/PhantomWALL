-- Create blocked_requests table
CREATE TABLE IF NOT EXISTS blocked_requests (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    full_url TEXT NOT NULL,
    domain VARCHAR(255) NOT NULL,
    request_type VARCHAR(64) NOT NULL,
    blocked BOOLEAN NOT NULL,
    action VARCHAR(64) NOT NULL,
    classification VARCHAR(64) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    risk_score INTEGER NOT NULL,
    third_party BOOLEAN NOT NULL,
    tab_url TEXT,
    referrer TEXT,
    top_features TEXT,
    explanation TEXT
);

-- Create domain_reputation table
CREATE TABLE IF NOT EXISTS domain_reputation (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) UNIQUE NOT NULL,
    times_seen INTEGER NOT NULL DEFAULT 0,
    times_blocked INTEGER NOT NULL DEFAULT 0,
    average_risk_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    classification VARCHAR(64) NOT NULL,
    first_seen TIMESTAMP WITH TIME ZONE NOT NULL,
    last_seen TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Create indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_blocked_requests_timestamp ON blocked_requests(timestamp);
CREATE INDEX IF NOT EXISTS idx_blocked_requests_user_id ON blocked_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_blocked_requests_domain ON blocked_requests(domain);
CREATE INDEX IF NOT EXISTS idx_blocked_requests_classification ON blocked_requests(classification);
CREATE INDEX IF NOT EXISTS idx_domain_reputation_domain ON domain_reputation(domain);
CREATE INDEX IF NOT EXISTS idx_domain_reputation_risk ON domain_reputation(average_risk_score);
