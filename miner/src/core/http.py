from http import HTTPStatus

import requests

from core.exceptions import AppException


def raise_http_error(
    response: requests.Response,
    errors: dict[HTTPStatus, AppException],
    default: AppException,
) -> None:
    status = response.status_code

    raise errors.get(status, default)
