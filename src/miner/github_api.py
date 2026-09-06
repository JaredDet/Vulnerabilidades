from urllib.parse import quote

import requests
from .models import Repository
from pydantic import ValidationError

GITHUB_API_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
DEFAULT_PAGE_SIZE = 10
REQUEST_TIMEOUT = 30


class GitHubAPIError(RuntimeError):
    """Falló una consulta a GitHub o su respuesta no es válida."""


class GitHubHTTPError(GitHubAPIError):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


def _http_error(response: requests.Response) -> GitHubHTTPError:
    status = response.status_code
    if status == 429 or (status == 403 and (
        response.headers.get("X-RateLimit-Remaining") == "0"
        or "Retry-After" in response.headers
    )):
        message = "Se alcanzó el límite de solicitudes de GitHub; intenta más tarde"
    else:
        message = {
            401: "GitHub rechazó el token; comprueba su validez y caducidad",
            403: "GitHub denegó el acceso; revisa permisos y restricciones de la organización",
            404: "La organización no existe o no es visible con este token",
        }.get(status, f"GitHub devolvió un error HTTP {status}")
    return GitHubHTTPError(status, message)


def _build_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }


def get_repository_languages(full_name: str, token: str) -> list[str]:
    """Consulta los lenguajes sin confundir un fallo con ausencia de código."""
    parts = full_name.strip().split("/")
    if len(parts) != 2 or not all(parts) or not token.strip():
        raise ValueError("Se requiere owner/repositorio y un token no vacío")
    path = "/repos/" + "/".join(quote(part, safe="")
                                for part in parts) + "/languages"
    with requests.Session() as client:
        client.headers.update(_build_headers(token.strip()))
        data = _get_json(client, path)
    if not isinstance(data, dict) or any(
        not isinstance(name, str) or not name.strip()
        or type(size) is not int or size < 0 for name, size in data.items()
    ):
        raise GitHubAPIError(
            "GitHub devolvió un listado de lenguajes inválido")
    return sorted(name for name, size in data.items() if size > 0)


def _parse_repository(data: object) -> Repository:
    try:
        return Repository.model_validate(data)
    except ValidationError:
        raise GitHubAPIError(
            "GitHub devolvió datos de repositorio inválidos") from None


def _get_json(client: requests.Session, path: str, params: dict | None = None) -> object:
    try:
        response = client.get(
            f"{GITHUB_API_URL}{path}",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.HTTPError as error:
        raise _http_error(error.response) from None
    except requests.Timeout:
        raise GitHubAPIError(
            "Se agotó el tiempo de espera al consultar GitHub") from None
    except requests.exceptions.JSONDecodeError:
        raise GitHubAPIError("GitHub devolvió JSON inválido") from None
    except requests.RequestException:
        raise GitHubAPIError(
            "No se pudo completar la conexión con GitHub") from None
    return data


def _get_repository_page(
    client: requests.Session, organization: str, page: int, page_size: int
) -> list[Repository]:
    data = _get_json(client, f"/orgs/{quote(organization, safe='')}/repos",
                     {"per_page": page_size, "page": page, "type": "all"})
    if not isinstance(data, list):
        raise GitHubAPIError(
            "GitHub devolvió una respuesta que no es una lista")
    return [_parse_repository(repository) for repository in data]


def get_organization_repositories(
    organization: str,
    token: str,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list[Repository]:
    """Devuelve los repositorios accesibles, o [] si no hay ninguno.

    Lanza ValueError por argumentos inválidos y GitHubAPIError por fallos de
    consulta o respuesta, sin devolver listas parciales.
    """
    organization = organization.strip()
    token = token.strip()

    if not organization:
        raise ValueError("La organización no puede estar vacía")

    if not token:
        raise ValueError("El token de GitHub no puede estar vacío")

    if not 1 <= page_size <= 100:
        raise ValueError("page_size debe estar entre 1 y 100")

    repositories: list[Repository] = []
    page = 1

    with requests.Session() as client:
        client.headers.update(_build_headers(token))

        while True:
            page_repositories = _get_repository_page(
                client, organization, page, page_size
            )
            repositories.extend(page_repositories)
            if len(page_repositories) < page_size:
                break

            page += 1

    return repositories
