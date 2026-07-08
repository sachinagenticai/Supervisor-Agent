CREATE TABLE IF NOT EXISTS application_user (
    id TEXT PRIMARY KEY,
    google_subject_id TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    display_name TEXT NOT NULL,
    profile_image_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_registry (
    id TEXT PRIMARY KEY,
    agent_code TEXT NOT NULL UNIQUE CHECK (agent_code IN ('PIPELINE_TROUBLESHOOTING', 'INFRA_PROVISIONING', 'FINOPS_OPTIMIZATION', 'PROJECT_MANAGEMENT')),
    agent_name TEXT NOT NULL,
    description TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL,
    tool_code TEXT NOT NULL UNIQUE CHECK (tool_code IN ('pipeline_troubleshooting_tool', 'infrastructure_provisioning_tool', 'finops_optimization_tool', 'project_management_tool')),
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS validation_record (
    id TEXT PRIMARY KEY,
    external_reference TEXT NOT NULL UNIQUE,
    source_system TEXT NOT NULL,
    record_type TEXT NOT NULL,
    record_title TEXT NOT NULL,
    expected_agent_code TEXT CHECK (expected_agent_code IN ('PIPELINE_TROUBLESHOOTING', 'INFRA_PROVISIONING', 'FINOPS_OPTIMIZATION', 'PROJECT_MANAGEMENT')),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS validation_run (
    id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL REFERENCES validation_record(id),
    initiated_by_user_id TEXT NOT NULL REFERENCES application_user(id),
    comments TEXT,
    execution_status TEXT NOT NULL CHECK (execution_status IN ('RUNNING', 'COMPLETED', 'ERROR')),
    detected_agent_code TEXT CHECK (detected_agent_code IN ('PIPELINE_TROUBLESHOOTING', 'INFRA_PROVISIONING', 'FINOPS_OPTIMIZATION', 'PROJECT_MANAGEMENT')),
    selected_tool_code TEXT CHECK (selected_tool_code IN ('pipeline_troubleshooting_tool', 'infrastructure_provisioning_tool', 'finops_optimization_tool', 'project_management_tool')),
    routing_reason TEXT,
    routing_confidence NUMERIC(5,4) CHECK (routing_confidence IS NULL OR (routing_confidence >= 0 AND routing_confidence <= 1)),
    final_verdict TEXT CHECK (final_verdict IN ('PASS', 'WARNING', 'FAIL')),
    final_reason TEXT,
    final_tag TEXT,
    final_confidence NUMERIC(5,4) CHECK (final_confidence IS NULL OR (final_confidence >= 0 AND final_confidence <= 1)),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS rule_result (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES validation_run(id) ON DELETE CASCADE,
    rule_code TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO')),
    passed BOOLEAN NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    message TEXT NOT NULL,
    tag TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm_judgement (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES validation_run(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    judge_verdict TEXT NOT NULL CHECK (judge_verdict IN ('PASS', 'WARNING', 'FAIL')),
    confidence NUMERIC(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    reason TEXT NOT NULL,
    findings JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_response JSONB NOT NULL DEFAULT '{}'::jsonb,
    prompt_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_event (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES validation_run(id) ON DELETE SET NULL,
    user_id TEXT REFERENCES application_user(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    event_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_validation_record_active ON validation_record(active);
CREATE INDEX IF NOT EXISTS idx_validation_record_source_type ON validation_record(source_system, record_type);
CREATE INDEX IF NOT EXISTS idx_validation_run_record ON validation_run(record_id);
CREATE INDEX IF NOT EXISTS idx_validation_run_status_verdict ON validation_run(execution_status, final_verdict);
CREATE INDEX IF NOT EXISTS idx_validation_run_started ON validation_run(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_rule_result_run ON rule_result(run_id);
CREATE INDEX IF NOT EXISTS idx_llm_judgement_run ON llm_judgement(run_id);
CREATE INDEX IF NOT EXISTS idx_audit_event_run ON audit_event(run_id, created_at);
