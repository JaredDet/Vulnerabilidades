from pathlib import Path


def workspace(
    organization: str,
    workspace_path: Path | None,
) -> Path:
    if (
        not organization
        or organization in {".", ".."}
        or any(char in organization for char in "/\\:")
    ):
        raise ValueError(
            "Nombre de organización inválido para el directorio de trabajo"
        )

    return (
        workspace_path
        if workspace_path is not None
        else Path("organizations") / organization / "work"
    )
