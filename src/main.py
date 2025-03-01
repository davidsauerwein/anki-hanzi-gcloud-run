import functions_framework
from flask import Request
from flask_httpauth import HTTPBasicAuth  # type: ignore

auth = HTTPBasicAuth()


@auth.verify_password  # type: ignore
def verify_password(username: str, password: str) -> bool:
    return username == "foo" and password == "bar"


@functions_framework.http
@auth.login_required  # type: ignore
def hello_get(request: Request) -> str:
    return "Hello World!"
