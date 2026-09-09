"""Exercise deploy orchestration with fake Docker/curl; never contact production."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "deploy.sh"


class DeployOrchestrationTest(unittest.TestCase):
    def run_deploy(self, *, bot=False, config=False, invalid_compose=False, failure=""):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compose = root / "infra/docker"
            compose.mkdir(parents=True)
            migrations = root / "apps/api/migrations"
            migrations.mkdir(parents=True)
            for revision in range(24, 28):
                (migrations / f"{revision:03d}_fixture.sql").write_text("-- fixture\n")
            bot_config = root / "operator-bot/api.env"
            if config:
                bot_config.parent.mkdir()
                bot_config.touch()
            command_log = root / "commands.jsonl"
            binaries = root / "bin"
            binaries.mkdir()
            docker = binaries / "docker"
            docker.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "args = sys.argv[1:]\n"
                "failure = os.environ['DEPLOY_TEST_FAILURE']\n"
                "with open(os.environ['DEPLOY_TEST_LOG'], 'a') as f:\n"
                " f.write(json.dumps(args) + '\\n')\n"
                "if args[0] == 'inspect':\n"
                " sys.exit(0 if os.environ['DEPLOY_TEST_BOT'] == '1' else 1)\n"
                "if args[0] == 'compose' and 'config' in args:\n"
                " sys.exit(int(os.environ['DEPLOY_TEST_INVALID']))\n"
                "if args[0] == 'exec' and 'pg_dump' in ' '.join(args):\n"
                " if failure == 'backup': print('incomplete'); sys.exit(0)\n"
                " print('-- fixture database dump\\n' * 500)\n"
                " if failure == 'backup_marker': sys.exit(0)\n"
                " print('-- PostgreSQL database dump complete')\n"
                "if failure == 'migration' and 'psql' in ' '.join(args): sys.exit(1)\n"
                "if failure == 'build' and 'build' in args: sys.exit(1)\n"
                "if failure == 'sdk' and '--entrypoint' in args: sys.exit(1)\n"
            )
            curl = binaries / "curl"
            curl.write_text(
                "#!/usr/bin/env python3\n"
                "import os, sys\n"
                "args = sys.argv[1:]\n"
                "url = args[-1]\n"
                "if os.environ['DEPLOY_TEST_FAILURE'] == 'health': sys.exit(22)\n"
                "if os.environ['DEPLOY_TEST_FAILURE'] == 'public' and '-w' in args: print('503'); sys.exit(0)\n"
                "if '-w' not in args: sys.exit(0)\n"
                "if url.endswith('/auth/register'): print('302')\n"
                "elif url.endswith('/auth/magic-link'): print('403')\n"
                "elif url.endswith('/documents/'): print('401')\n"
                "elif url.endswith('/documents'):\n"
                " print('307 https://app.thesica.co/api/v1/documents/')\n"
                "else: print('200')\n"
            )
            sleep = binaries / "sleep"
            sleep.write_text("#!/bin/sh\nexit 0\n")
            for binary in (docker, curl, sleep):
                binary.chmod(0o755)
            script = root / "deploy.sh"
            assert "ROOT=/opt/thesica" in SCRIPT.read_text()
            script.write_text(
                SCRIPT.read_text()
                .replace("ROOT=/opt/thesica", f'ROOT="{root}"')
                .replace("/etc/thesica/operator-bot/api.env", str(bot_config))
            )
            env = dict(
                os.environ,
                PATH=f"{binaries}{os.pathsep}{os.environ['PATH']}",
                DEPLOY_TEST_LOG=str(command_log),
                DEPLOY_TEST_BOT=str(int(bot)),
                DEPLOY_TEST_INVALID=str(int(invalid_compose)),
                DEPLOY_TEST_FAILURE=failure,
            )
            result = subprocess.run(
                ["bash", str(script)],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            commands = (
                [json.loads(line) for line in command_log.read_text().splitlines()]
                if command_log.exists()
                else []
            )
            return result, commands

    def test_installed_bot_overlay_is_kept_for_every_compose_action(self):
        result, commands = self.run_deploy(bot=True, config=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        compose = [args for args in commands if args[0] == "compose"]
        self.assertTrue(compose)
        for args in compose:
            self.assertIn("docker-compose.operator-bot.yml", args)
            self.assertEqual(args[1:3], ["-p", "docker"])
        restart = next(args for args in compose if "up" in args)
        self.assertEqual(
            restart[restart.index("up") :], ["up", "-d", "--no-deps", "api", "web"]
        )

    def test_installation_without_bot_uses_only_base_compose(self):
        result, commands = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(any("build" in args for args in commands))
        self.assertFalse(
            any("docker-compose.operator-bot.yml" in args for args in commands)
        )

    def test_missing_installed_bot_configuration_stops_before_mutations(self):
        result, commands = self.run_deploy(bot=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, [["inspect", "docker-operator-bot-1"]])

    def test_invalid_compose_stops_before_backup_migrations_or_build(self):
        result, commands = self.run_deploy(config=True, invalid_compose=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][-2:], ["config", "--quiet"])


if __name__ == "__main__":
    unittest.main()
