"""Production compose and actual server deploy script contracts; all shell commands are stubbed."""

import importlib.util
import subprocess
from pathlib import Path

import pytest
import yaml

from app.core.config import Settings
from tests.release_profile import RELEASE_PROFILE, release_profile_env

REPO_ROOT = Path(__file__).resolve().parents[3]
PROD_COMPOSE = REPO_ROOT / "infra/docker/docker-compose.prod.yml"
DEV_COMPOSE = REPO_ROOT / "infra/docker/docker-compose.yml"
DEPLOY_SCRIPT = REPO_ROOT / "infra/deploy.sh"
CI_WORKFLOW = REPO_ROOT / ".github/workflows/ci.yml"


def _prod_compose() -> dict:
    return yaml.safe_load(PROD_COMPOSE.read_text(encoding="utf-8"))


def _api_environment() -> dict[str, str]:
    entries = _prod_compose()["services"]["api"]["environment"]
    return dict(entry.split("=", 1) for entry in entries)


@pytest.fixture
def deploy():
    spec = importlib.util.spec_from_file_location(
        "offline_deploy", REPO_ROOT / "infra/tests/test_deploy.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DeployOrchestrationTest().run_deploy


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

    for name, expected in release_profile_env().items():
        assert environment[name] == expected
    assert environment["RELEASE_PRIMARY_DETECTOR_NAME"] == "Compilatio"


def test_release_profile_is_a_valid_settings_combination() -> None:
    runtime = Settings(_env_file=None, **RELEASE_PROFILE)

    for name, expected in RELEASE_PROFILE.items():
        assert getattr(runtime, name) == expected


def test_deploy_backs_up_and_checks_schema_and_sdk_before_restart(deploy):
    result, commands = deploy()
    assert result.returncode == 0, result.stdout + result.stderr
    dump = next(i for i, c in enumerate(commands) if "pg_dump" in " ".join(c))
    tags = [i for i, c in enumerate(commands) if c[0] == "tag"]
    migrations = [i for i, c in enumerate(commands) if "psql" in " ".join(c)]
    build = next(i for i, c in enumerate(commands) if "build" in c)
    sdk = next(i for i, c in enumerate(commands) if "--entrypoint" in c)
    restart = next(i for i, c in enumerate(commands) if "up" in c)
    assert len(tags) == 2 and len(migrations) == 4
    assert (
        dump
        < min(tags)
        < max(tags)
        < min(migrations)
        < max(migrations)
        < build
        < sdk
        < restart
    )
    assert all("ON_ERROR_STOP=1" in " ".join(commands[i]) for i in migrations)
    assert not any("down" in c for c in commands)
    assert commands[restart][-5:] == ["up", "-d", "--no-deps", "api", "web"]


@pytest.mark.parametrize(
    "failure", ["backup", "backup_marker", "migration", "build", "sdk"]
)
def test_deploy_failure_before_restart_keeps_running_containers(deploy, failure):
    result, commands = deploy(failure=failure)
    assert result.returncode != 0
    assert not any("up" in c or "down" in c for c in commands)
    if failure.startswith("backup"):
        assert not any(c[0] == "tag" or "psql" in " ".join(c) for c in commands)


@pytest.mark.parametrize("failure", ["health", "public"])
def test_deploy_health_failures_return_nonzero_and_print_rollback(deploy, failure):
    result, commands = deploy(failure=failure)
    assert result.returncode != 0
    assert any("up" in c for c in commands)
    assert "Відкат:" in result.stdout and "ДЕПЛОЙ УСПІШНИЙ" not in result.stdout


def test_deploy_keeps_operator_overlay_for_every_compose_call(deploy):
    result, commands = deploy(bot=True, config=True)
    assert result.returncode == 0, result.stdout + result.stderr
    compose = [c for c in commands if c[0] == "compose"]
    assert compose and all("docker-compose.operator-bot.yml" in c for c in compose)


@pytest.mark.parametrize(
    "options", [{"bot": True}, {"config": True, "invalid_compose": True}]
)
def test_deploy_invalid_configuration_stops_before_any_mutation(deploy, options):
    result, commands = deploy(**options)
    assert result.returncode != 0
    assert len(commands) == 1
    assert commands[0][0] == "inspect" or commands[0][-2:] == ["config", "--quiet"]


def test_actual_deploy_script_and_compose_contracts_parse():
    result = subprocess.run(
        ["bash", "-n", str(DEPLOY_SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    assert _prod_compose()
