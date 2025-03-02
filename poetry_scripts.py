import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

SOURCES = ["src/", "tests/", "poetry_scripts.py"]


def run(*cmd: str) -> None:
    """Run given command as subprocess and exit with 1 if it fails."""
    if subprocess.run([*cmd]).returncode != 0:
        sys.exit(1)


def black_check() -> None:
    run("poetry", "run", "black", "--check", *SOURCES)


def black_format() -> None:
    run("poetry", "run", "black", *SOURCES)


def flake8() -> None:
    # flake8 cannot be configured in pyproject.toml, so we pass everything we need here.
    # https://black.readthedocs.io/en/stable/guides/using_black_with_other_tools.html#minimal-configuration
    run("poetry", "run", "flake8", "--ignore=E203,E501,E701,E704", *SOURCES)


def isort_check() -> None:
    run("poetry", "run", "isort", "--check-only", *SOURCES)


def isort_format() -> None:
    run("poetry", "run", "isort", *SOURCES)


def mypy() -> None:
    run("poetry", "run", "mypy", *SOURCES)


def lint() -> None:
    black_check()
    isort_check()
    flake8()
    mypy()
    print()
    print("All checks successful!")


def format() -> None:
    black_format()
    isort_format()
    print()
    print("Formatted code successfully!")


def deploy() -> None:
    with TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)

        shutil.copytree(
            "src",
            tmpdir,
            ignore=shutil.ignore_patterns("*.pyc", "__pycache__"),
            dirs_exist_ok=True,
        )

        run(
            "poetry",
            "export",
            "--without-hashes",
            "--format",
            "requirements.txt",
            "--output",
            str(tmpdir / "requirements.txt"),
        )

        code_archive = Path(
            shutil.make_archive(
                base_name=str(tmpdir / "function"),
                format="zip",
                root_dir=str(tmpdir),
                base_dir=str(tmpdir),
            )
        )

        with open(
            Path.home() / ".config/anki-hanzi/google-application-credentials.json"
        ) as credentials_json:
            project_id = json.load(credentials_json)["project_id"]

        run(
            "gcloud",
            "run",
            "deploy",
            "anki-hanzi",
            "--project",
            project_id,
            "--source",
            str(code_archive),
            "--function",
            "hello_get",
            "--base-image",
            "python312",
            "--allow-unauthenticated",
            "--max-instances",
            "1",
            "--concurrency",
            "1",
        )
