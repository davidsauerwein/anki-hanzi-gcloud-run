import logging
import shutil
from functools import cache
from pathlib import Path

import anki_hanzi
import functions_framework

# google-cloud-storage apparently does not have full typing support.
# This fixes mypy errors while still allow to type check other google cloud modules.
# https://github.com/googleapis/python-cloud-core/issues/166
import google.cloud.storage as storage  # type: ignore
import requests
from flask import Request, Response, jsonify
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
def run_anki_hanzi(request: Request) -> tuple[Response, int]:
    path = request.path.removeprefix("/")
    components = path.split("/")

    # Path must be /process/<deck>. A bit hacky honestly, but with the functions framework there is no control over the
    # Flask app to set any routes. This could be fixed by switching to Google Cloud Run, but I don't think that's worth
    # the effort right now.
    # Guarding against a specific path avoids loading the collection when browsers request random files such as a
    # favicon.
    if len(components) != 2 or components[0] != "process":
        return jsonify(error="Not found"), 404

    deck = components[1]

    anki_username = get_secret("anki-username")
    anki_password = get_secret("anki-password")

    anki_data_dir = Path("/tmp/anki-hanzi")
    anki_data_dir.mkdir(parents=True, exist_ok=True)
    collection_file = anki_data_dir / "collection.anki2"

    storage_client = storage.Client()
    anki_data_bucket = storage_client.bucket(f"{get_project_id()}-anki-data")
    cache_archive = anki_data_dir.with_suffix(".tar")
    cache_blob = anki_data_bucket.blob(cache_archive.name)

    # Download the collection if we already cached it.
    if cache_blob.exists():
        logging.info("Downloading cached collection.")
        cache_blob.download_to_filename(str(cache_archive))
        shutil.unpack_archive(filename=cache_archive, extract_dir=anki_data_dir)
        if not collection_file.is_file():
            logging.warning("Cached archive does not contain collection.")
        logging.info("Successfully downloaded cached collection.")
    else:
        logging.info("Collection not cached. Performing full sync.")

    try:
        result = anki_hanzi.run(
            anki_username=anki_username,
            anki_password=anki_password,
            anki_collection_path=collection_file,
            google_cloud_project_id=get_project_id(),
            deck_name=deck,
            force=False,
            overwrite_target_fields=False,
        )
    except anki_hanzi.AnkiDeckNotFoundException:
        return jsonify(error=f"Anki deck {deck} does not exist."), 404

    logging.info("Uploading collection to cache.")
    shutil.make_archive(
        base_name=str(anki_data_dir), format="tar", root_dir=anki_data_dir
    )
    cache_blob.upload_from_filename(str(cache_archive))
    logging.info("Successfully uploaded collection.")

    return jsonify(result), 200
