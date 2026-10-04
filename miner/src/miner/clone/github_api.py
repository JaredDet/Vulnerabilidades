from collections.abc import Iterator
from http import HTTPStatus
from urllib.parse import quote

import requests
from pydantic import ValidationError

from core.http import raise_http_error

from .errors import CloneErrors
from .models import Repository

GITHUB_API_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
PAGE_SIZE = 100
REQUEST_TIMEOUT = 30


def _build_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }


def _get_json(
    client: requests.Session,
    path: str,
    params: dict | None = None,
) -> object:
    try:
        response = client.get(
            f"{GITHUB_API_URL}{path}",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    except requests.HTTPError as error:
        response = error.response

        if response.status_code == HTTPStatus.FORBIDDEN and (
            response.headers.get("X-RateLimit-Remaining") == "0"
            or "Retry-After" in response.headers
        ):
            raise CloneErrors.GitHubRateLimit from None

        raise_http_error(
            response,
            {
                HTTPStatus.UNAUTHORIZED: CloneErrors.GitHubUnauthorized,
                HTTPStatus.FORBIDDEN: CloneErrors.GitHubForbidden,
                HTTPStatus.NOT_FOUND: CloneErrors.GitHubNotFound,
                HTTPStatus.TOO_MANY_REQUESTS: CloneErrors.GitHubRateLimit,
            },
            CloneErrors.GitHubRequestFailed,
        )

    except requests.RequestException:
        raise CloneErrors.GitHubRequestFailed from None


def _get_repository_page(
    client: requests.Session,
    organization: str,
    page: int,
    page_size: int,
) -> list[Repository]:
    data = _get_json(
        client,
        f"/orgs/{quote(organization, safe='')}/repos",
        {
            "per_page": page_size,
            "page": page,
            "type": "public",
        },
    )

    if not isinstance(data, list):
        raise CloneErrors.GitHubRequestFailed

    try:
        return [Repository.model_validate(repository) for repository in data]
    except ValidationError:
        raise CloneErrors.GitHubRequestFailed from None


def get_organization_repository_pages(
    organization: str,
    token: str,
    page_size: int,
) -> Iterator[list[Repository]]:
    """Entrega una página de repositorios públicos a la vez."""
    organization = organization.strip()
    token = token.strip()

    if not organization:
        raise CloneErrors.OrganizationRequired

    if not token:
        raise CloneErrors.TokenRequired

    page = 1

    with requests.Session() as client:
        client.headers.update(_build_headers(token))

        while True:
            page_repositories = _get_repository_page(
                client,
                organization,
                page,
                page_size,
            )

            if page_repositories:
                yield page_repositories

            if len(page_repositories) < page_size:
                break

            page += 1


def get_organization_repositories(
    organization: str,
    token: str,
    page_size: int = PAGE_SIZE,
) -> list[Repository]:
    """Devuelve los repositorios accesibles de una organización."""
    return [
        repository
        for repositories in get_organization_repository_pages(
            organization,
            token,
            page_size,
        )
        for repository in repositories
    ]
