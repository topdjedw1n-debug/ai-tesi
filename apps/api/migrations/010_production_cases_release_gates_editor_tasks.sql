-- Phase 2: internal production cases, release gates, and editor tasks.

CREATE TABLE IF NOT EXISTS production_cases (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    client_user_id INTEGER NOT NULL REFERENCES users(id),
    manager_id INTEGER REFERENCES users(id),
    editor_id INTEGER REFERENCES users(id),
    deadline_at TIMESTAMPTZ,
    citation_style VARCHAR(50),
    requirements_text TEXT,
    intake_status VARCHAR(50) NOT NULL DEFAULT 'draft',
    generation_status VARCHAR(50) NOT NULL DEFAULT 'not_started',
    qa_status VARCHAR(50) NOT NULL DEFAULT 'no_data',
    editorial_status VARCHAR(50) NOT NULL DEFAULT 'not_started',
    payment_status VARCHAR(50) NOT NULL DEFAULT 'not_required',
    delivery_status VARCHAR(50) NOT NULL DEFAULT 'not_ready',
    release_status VARCHAR(50) NOT NULL DEFAULT 'not_ready',
    human_minutes_budget INTEGER NOT NULL DEFAULT 0,
    human_minutes_used INTEGER NOT NULL DEFAULT 0,
    cost_cents INTEGER NOT NULL DEFAULT 0,
    release_notes TEXT,
    released_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_production_cases_document_id UNIQUE (document_id)
);

CREATE INDEX IF NOT EXISTS ix_production_cases_document_id ON production_cases(document_id);
CREATE INDEX IF NOT EXISTS ix_production_cases_client_user_id ON production_cases(client_user_id);
CREATE INDEX IF NOT EXISTS ix_production_cases_manager_id ON production_cases(manager_id);
CREATE INDEX IF NOT EXISTS ix_production_cases_editor_id ON production_cases(editor_id);
CREATE INDEX IF NOT EXISTS ix_production_cases_release_status ON production_cases(release_status);

CREATE TABLE IF NOT EXISTS release_gate_results (
    id SERIAL PRIMARY KEY,
    production_case_id INTEGER NOT NULL REFERENCES production_cases(id) ON DELETE CASCADE,
    gate_key VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'no_data',
    severity VARCHAR(50) NOT NULL DEFAULT 'blocking',
    blocking BOOLEAN NOT NULL DEFAULT TRUE,
    source VARCHAR(100),
    summary TEXT,
    evidence JSONB,
    override_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    override_reason TEXT,
    overridden_by_id INTEGER REFERENCES users(id),
    overridden_at TIMESTAMPTZ,
    last_checked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_release_gate_case_gate UNIQUE (production_case_id, gate_key)
);

CREATE INDEX IF NOT EXISTS ix_release_gate_results_case_id ON release_gate_results(production_case_id);
CREATE INDEX IF NOT EXISTS ix_release_gate_results_gate_key ON release_gate_results(gate_key);

CREATE TABLE IF NOT EXISTS editor_tasks (
    id SERIAL PRIMARY KEY,
    production_case_id INTEGER NOT NULL REFERENCES production_cases(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_id INTEGER REFERENCES document_sections(id) ON DELETE SET NULL,
    assigned_editor_id INTEGER NOT NULL REFERENCES users(id),
    created_by_id INTEGER REFERENCES users(id),
    source_gate VARCHAR(100),
    finding_key VARCHAR(100),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    resolution_notes TEXT,
    minutes_spent INTEGER NOT NULL DEFAULT 0,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_editor_tasks_case_id ON editor_tasks(production_case_id);
CREATE INDEX IF NOT EXISTS ix_editor_tasks_assigned_editor_id ON editor_tasks(assigned_editor_id);
CREATE INDEX IF NOT EXISTS ix_editor_tasks_status ON editor_tasks(status);
