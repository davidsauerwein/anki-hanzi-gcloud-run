from functools import cache
from pathlib import Path
from typing import Any

import anki_hanzi
import functions_framework
import requests
from flask import Request
from flask_httpauth import HTTPBasicAuth  # type: ignore
from google.cloud import secretmanager

auth = HTTPBasicAuth()
secrets = secretmanager.SecretManagerServiceClient()

USERNAME = "anki-hanzi"


@cache
def get_project_id() -> str:
    response = requests.get(
        "http://metadata.google.internal/computeMetadata/v1/project/project-id",
        headers={"Metadata-Flavor": "Google"},
    )
    response.raise_for_status()
    return response.text


def get_secret(name: str) -> str:
    full_name = f"projects/{get_project_id()}/secrets/{name}/versions/latest"
    response = secrets.access_secret_version(name=full_name)
    return response.payload.data.decode()


@auth.verify_password  # type: ignore
def verify_password(username: str, password: str) -> bool:
    expected_password = get_secret("anki-hanzi-run-function-password")
    return username == USERNAME and password == expected_password


@functions_framework.http
@auth.login_required  # type: ignore
def run_anki_hanzi(request: Request) -> dict[str, Any]:
    # We assume a path of process/<deckname>
    # FIXME Do proper error handle and figure out how to switch to full flask
    path = request.path.removeprefix("/")
    process, deck = path.split("/")
    assert process == "process"

    anki_username = get_secret("anki-username")
    anki_password = get_secret("anki-password")

    anki_data_dir = Path("/tmp/anki-hanzi")
    anki_data_dir.mkdir(parents=True, exist_ok=True)

    result = anki_hanzi.run(
        anki_username=anki_username,
        anki_password=anki_password,
        anki_collection_path=anki_data_dir / "collection.anki2",
        google_cloud_project_id=get_project_id(),
        deck_name=deck,
        force=False,
        overwrite_target_fields=False,
    )
    return dict(result)
