import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PROD_COMPOSE = REPO_ROOT / "infra" / "docker" / "docker-compose.prod.yml"
DEV_COMPOSE = REPO_ROOT / "infra" / "docker" / "docker-compose.yml"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-aws.yml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _prod_compose() -> dict:
    return yaml.safe_load(PROD_COMPOSE.read_text(encoding="utf-8"))


def _api_environment() -> dict[str, str]:
    entries = _prod_compose()["services"]["api"]["environment"]
    return dict(entry.split("=", 1) for entry in entries)


def _workflow_text() -> str:
    return DEPLOY_WORKFLOW.read_text(encoding="utf-8")


def _deployment_step_script() -> str:
    workflow = yaml.safe_load(_workflow_text())
    steps = workflow["jobs"]["deploy"]["steps"]
    step = next(
        item for item in steps if item["name"] == "Deploy the verified revision"
    )
    return step["run"]


def _dotenv_writer_code() -> str:
    script = _deployment_step_script()
    match = re.search(r"python3 <<'PY'\n(?P<code>.*?)\nPY(?:\n|$)", script, re.DOTALL)
    assert match is not None
    return match.group("code")


def _writer_environment(path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "DEPLOY_ENV_FILE": str(path),
            "PUBLIC_FRONTEND_URL": "https://app.example.com/",
            "PUBLIC_API_URL": "https://api.example.com",
            "POSTGRES_DB": "tesi_db",
            "POSTGRES_USER": "tesi+user",
            "POSTGRES_PASSWORD": "pa$ss:@/'\\word",
            "MINIO_ROOT_USER": "storage-user",
            "MINIO_ROOT_PASSWORD": "storage-$ecret-'value",
            "SECRET_KEY": "s" * 40 + "$'",
            "JWT_SECRET": "j" * 40 + "$'",
            "OPENAI_API_KEY": "openai-$value",
            "ANTHROPIC_API_KEY": "",
            "STRIPE_SECRET_KEY": "",
            "STRIPE_PUBLISHABLE_KEY": "",
            "STRIPE_WEBHOOK_SECRET": "",
            "RESEND_API_KEY": "",
            "COPYSCAPE_API_KEY": "",
            "COPYSCAPE_USERNAME": "",
            "GPTZERO_API_KEY": "",
            "ORIGINALITY_AI_API_KEY": "",
            "SEMANTIC_SCHOLAR_API_KEY": "",
            "OPENALEX_API_KEY": "",
        }
    )
    return environment


def test_prod_api_uses_minio_root_credentials_without_insecure_fallback() -> None:
    environment = _api_environment()

    assert environment["MINIO_ACCESS_KEY"] == (
        "${MINIO_ROOT_USER:?MINIO_ROOT_USER is required}"
    )
    assert environment["MINIO_SECRET_KEY"] == (
        "${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD is required}"
    )
    assert "minioadmin" not in PROD_COMPOSE.read_text(encoding="utf-8")


def test_generated_files_are_not_exposed_by_anonymous_bucket_policy() -> None:
    dev_compose = DEV_COMPOSE.read_text(encoding="utf-8")
    prod = _prod_compose()
    setup = prod["services"]["minio-setup"]
    setup_command = setup["command"][-1]

    assert "policy set public" not in dev_compose
    assert "anonymous set none" in dev_compose
    assert "mb --ignore-existing" in setup_command
    assert "anonymous set none" in setup_command
    assert setup["depends_on"]["minio"]["condition"] == "service_healthy"
    assert prod["services"]["api"]["depends_on"]["minio-setup"]["condition"] == (
        "service_completed_successfully"
    )


def test_prod_academic_quality_contract_is_explicit_and_fail_closed() -> None:
    environment = _api_environment()

    assert environment["MVP_FREE_GENERATION_MAX_PAGES"] == (
        "${MVP_FREE_GENERATION_MAX_PAGES:-50}"
    )
    assert environment["QUALITY_GATES_ENABLED"] == "true"
    assert environment["PARTIAL_COMPLETION_ENABLED"] == "false"
    assert environment["SOURCE_GROUNDING_ENABLED"] == "true"
    assert environment["GROUNDING_GATE_ENABLED"] == "true"
    assert environment["GROUNDING_GATE_POLICY"] == "strict"
    assert environment["CITATION_VERIFICATION_ENABLED"] == "true"
    assert environment["CITATION_VERIFICATION_POLICY"] == "strict"
    assert environment["CLAIM_VERIFICATION_ENABLED"] == "true"
    assert environment["QUALITY_PANEL_ENABLED"] == "true"
    assert environment["HUMANIZER_ENABLED"] == "false"
    assert environment["RELEASE_PRIMARY_DETECTOR_NAME"] == "Compilatio"


def test_deploy_only_uses_an_exact_revision_that_passed_ci() -> None:
    workflow = _workflow_text()
    trigger_section = workflow.split("\npermissions:", 1)[0]
    ci_workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_run:" in trigger_section
    assert 'workflows: ["CI Quality Gates"]' in trigger_section
    assert "workflow_dispatch:" in trigger_section
    assert "\n  push:" not in trigger_section
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "github.event.workflow_run.event == 'push'" in workflow
    assert "github.event.workflow_run.head_sha" in workflow
    assert "${{ inputs.commit_sha }}" in workflow
    assert 'deploy_mode="automatic"' in workflow
    assert 'deploy_mode="manual"' in workflow
    assert "actions/workflows/ci.yml/runs" in workflow
    assert "-f event=push" in workflow
    assert "-f status=success" in workflow
    assert "git merge-base --is-ancestor" in workflow
    assert 'if [ "$DEPLOY_SHA" != "$branch_head" ]' in workflow
    assert "skipping this stale automatic deploy" in workflow
    assert 'git reset --hard "$DEPLOY_SHA"' in workflow
    assert "git reset --hard origin/main" not in workflow
    assert "cancel-in-progress: false" in workflow
    assert "branches: [main, develop, production]" in ci_workflow


def test_deploy_pins_the_ssh_host_instead_of_trusting_first_contact() -> None:
    workflow = _workflow_text()

    assert "EC2_KNOWN_HOSTS: ${{ secrets.EC2_KNOWN_HOSTS }}" in workflow
    assert "printf '%s\\n' \"$EC2_KNOWN_HOSTS\"" in workflow
    assert "ssh-keygen -F" in workflow
    assert "StrictHostKeyChecking=yes" in workflow
    assert "ssh-keyscan" not in workflow
    assert "StrictHostKeyChecking=no" not in workflow


def test_deploy_env_writer_quotes_values_and_url_encodes_database_credentials(
    tmp_path: Path,
) -> None:
    output = tmp_path / "production.env"
    result = subprocess.run(
        [sys.executable, "-c", _dotenv_writer_code()],
        env=_writer_environment(output),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    content = output.read_text(encoding="utf-8")
    assert (
        "DATABASE_URL='postgresql+asyncpg://tesi%2Buser:"
        "pa%24ss%3A%40%2F%27%5Cword@postgres:5432/tesi_db'"
    ) in content
    assert "POSTGRES_PASSWORD='pa$ss:@/\\'\\\\word'" in content
    assert "OPENAI_API_KEY='openai-$value'" in content
    assert "CORS_ALLOWED_ORIGINS='https://app.example.com'" in content
    assert "NEXT_PUBLIC_API_URL='https://api.example.com'" in content


@pytest.mark.parametrize(
    "frontend_url",
    [
        "http://app.example.com",
        "https://127.0.0.1",
        "https://app.example.com/path",
        "https://app.example.com:not-a-port",
        "https://app example.com",
    ],
)
def test_deploy_env_writer_rejects_non_public_https_origins(
    tmp_path: Path,
    frontend_url: str,
) -> None:
    output = tmp_path / "production.env"
    environment = _writer_environment(output)
    environment["PUBLIC_FRONTEND_URL"] = frontend_url

    result = subprocess.run(
        [sys.executable, "-c", _dotenv_writer_code()],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert not output.exists()


def test_deploy_env_writer_rejects_multiline_secret_before_creating_file(
    tmp_path: Path,
) -> None:
    output = tmp_path / "production.env"
    environment = _writer_environment(output)
    environment["JWT_SECRET"] = "valid-prefix\ninjected=value"

    result = subprocess.run(
        [sys.executable, "-c", _dotenv_writer_code()],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "line breaks" in result.stderr
    assert not output.exists()


def test_deploy_removes_temporary_secrets_and_checks_public_https() -> None:
    workflow = _workflow_text()

    assert "ai-thesis-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}.env.production" in workflow
    assert "trap cleanup_local_secret EXIT" in workflow
    assert "trap cleanup_remote_secret EXIT" in workflow
    assert 'rm -f "$REMOTE_ENV_FILE"' in workflow
    assert "PUBLIC_FRONTEND_URL: ${{ vars.PUBLIC_FRONTEND_URL }}" in workflow
    assert "PUBLIC_API_URL: ${{ vars.PUBLIC_API_URL }}" in workflow
    assert 'parsed.scheme != "https"' in workflow
    assert "--proto '=https' --tlsv1.2" in workflow
    assert "http://$EC2_HOST" not in workflow


def test_deploy_bootstraps_infrastructure_and_schema_before_api_and_web() -> None:
    workflow = _workflow_text()

    build = workflow.index("compose build api web")
    infrastructure = workflow.index("compose up -d postgres redis minio")
    minio_setup = workflow.index("compose run --rm --no-deps minio-setup")
    database_init = workflow.index("from app.core.database import init_db")
    migrations = workflow.index("for migration in ../../apps/api/migrations/")
    api_start = workflow.index("compose up -d --no-deps --force-recreate api")
    web_start = workflow.index("compose up -d --no-deps --force-recreate web")

    assert build < infrastructure < minio_setup < database_init < migrations
    assert migrations < api_start < web_start
    assert "docker-compose -f docker-compose.prod.yml down" not in workflow
    assert "--set ON_ERROR_STOP=1 --single-transaction" in workflow
    assert 'if [ "$migration_count" -eq 0 ]' in workflow
    assert "wait_healthy api 240" in workflow
    assert "wait_healthy web 240" in workflow


def test_deploy_and_compose_yaml_are_parseable() -> None:
    assert yaml.safe_load(DEPLOY_WORKFLOW.read_text(encoding="utf-8"))
    assert yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    assert _prod_compose()
