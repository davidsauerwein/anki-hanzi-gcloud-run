from functools import cache

import functions_framework
import requests
from flask import Request
from flask_httpauth import HTTPBasicAuth  # type: ignore
from google.cloud import secretmanager

auth = HTTPBasicAuth()

USERNAME = "anki-hanzi"


@cache
def get_project_id() -> str:
    response = requests.get(
        "http://metadata.google.internal/computeMetadata/v1/project/project-id",
        headers={"Metadata-Flavor": "Google"},
    )
    response.raise_for_status()
    return response.text


@auth.verify_password  # type: ignore
def verify_password(username: str, password: str) -> bool:
    secrets = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/{get_project_id()}/secrets/anki-hanzi-run-function-password/versions/latest"
    response = secrets.access_secret_version(name=secret_name)
    expected_password = response.payload.data.decode("UTF-8")

    return username == USERNAME and password == expected_password


@functions_framework.http
@auth.login_required  # type: ignore
def hello_get(request: Request) -> str:
    return "Hello World!"
