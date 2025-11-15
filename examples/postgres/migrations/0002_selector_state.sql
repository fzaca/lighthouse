-- Track selector cursor per pool/strategy for round-robin acquisitions.
CREATE TABLE IF NOT EXISTS pool_selector_state (
    pool_id UUID NOT NULL REFERENCES proxy_pool(id) ON DELETE CASCADE,
    strategy VARCHAR(32) NOT NULL,
    last_proxy_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (pool_id, strategy)
);

CREATE OR REPLACE FUNCTION trg_pool_selector_state_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS pool_selector_state_set_updated_at ON pool_selector_state;

CREATE TRIGGER pool_selector_state_set_updated_at
BEFORE UPDATE ON pool_selector_state
FOR EACH ROW
EXECUTE PROCEDURE trg_pool_selector_state_updated_at();
