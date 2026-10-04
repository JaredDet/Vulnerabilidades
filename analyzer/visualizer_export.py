"""Export notebook analyses as a versioned, self-contained Visualizer input."""

from __future__ import annotations

import hashlib
import json
import math
import numbers
import os
from pathlib import Path
import platform
import re
import tempfile
from datetime import datetime, timezone
from importlib.metadata import version
from typing import Any

import pandas as pd


SCHEMA_VERSION = "1.0"

# Table names are stable public identifiers, independent of plot presentation.
TABLES = {
    1: {"concentracion": ("concentracion", "Repositorio y herramienta; incluye el estado del análisis.")},
    2: {
        "reglas_globales": ("reglas_globales", "Regla de CodeQL; todas las reglas observadas."),
        "reglas_compartidas": ("reglas_compartidas", "Regla presente en al menos dos repositorios."),
        "reglas_por_repositorio": ("reglas_por_repositorio", "Regla y repositorio; ranking completo, sin limitar al top 5."),
    },
    3: {
        "cobertura_puntajes": ("cobertura_puntajes", "Herramienta; cobertura y proporción de hallazgos puntuados."),
        "puntajes_por_repositorio": ("metricas_pregunta_3", "Repositorio y herramienta; máximo representativo por hallazgo."),
        "severidades": ("distribucion_severidades", "Herramienta, clase de severidad y etiqueta original."),
        "puntajes": ("distribucion_puntajes", "Herramienta, sistema, versión y puntaje representativo."),
    },
    4: {
        "paquetes": ("ranking_paquetes_grype", "Nombre y tipo de paquete; incluye los de un solo repositorio."),
        "identificadores": ("ranking_identificadores_grype", "Identificador original de Grype; sin resolver alias CVE/GHSA."),
        "paquetes_compartidos": ("paquetes_compartidos", "Paquete y ecosistema presentes en varios repositorios."),
        "identificadores_compartidos": ("vulnerabilidades_compartidas", "Identificador presente en varios repositorios."),
        "detalle_paquetes_compartidos": ("detalle_paquetes_compartidos", "Registros originales asociados a paquetes compartidos."),
    },
    5: {"relacion_conteos": ("conteos_relacion", "Repositorio con CodeQL y Grype analyzed; incluye rangos con empates promedio.")},
    6: {
        "concentracion_archivos": ("resumen_archivos", "Repositorio; cobertura de ubicación y unión de hallazgos del top 3."),
        "archivos": ("hallazgos_por_archivo", "Repositorio y archivo; un hallazgo cuenta una vez por archivo."),
        "top_archivos": ("top_archivos", "Hasta tres archivos por repositorio; desempate por ruta."),
    },
    7: {
        "cobertura_sbom": ("cobertura_sbom", "Repositorio; distingue inventarios vacíos, fallidos, ausentes e inválidos."),
        "ecosistemas": ("resumen_ecosistemas", "Ecosistema; registros de componentes, incluidos los sin coincidencias de Grype."),
        "ecosistemas_por_repositorio": ("componentes_por_ecosistema", "Repositorio y ecosistema; conteos y composición local."),
    },
    8: {
        "componentes_por_repositorio": ("resumen_componentes", "Repositorio; inventario, coincidencias, cobertura y proporción afectada."),
        "componentes": ("detalle_componentes", "Registro de componente; identificadores de Grype asociados sin multiplicar el numerador."),
        "hallazgos_sin_correspondencia": ("grype_sin_correspondencia", "Registros de Grype sin clave compatible en el SBOM."),
    },
    9: {
        "paquetes_compartidos": ("paquetes_sbom_compartidos", "Ecosistema y nombre normalizado; al menos dos repositorios."),
        "versiones_compartidas": ("versiones_sbom_compartidas", "Ecosistema, nombre normalizado y versión textual exacta."),
        "detalle_compartidos": ("detalle_compartidos_sbom", "Componentes de paquetes compartidos, con o sin coincidencias de Grype."),
    },
    10: {
        "cobertura_ci": ("cobertura_ci", "Repositorio; exige resultado explícito del lenguaje actions."),
        "reglas_ci": ("reglas_ci", "Regla de Actions observada; los estados parciales permanecen en el detalle."),
        "reglas_ci_compartidas": ("reglas_ci_compartidas", "Regla de Actions presente en al menos dos repositorios."),
        "severidades_ci": ("severidades_ci", "Nivel SARIF; no representa un puntaje CVSS."),
        "hallazgos_ci": ("hallazgos_ci", "Hallazgo observado por lenguaje Actions, con archivo y estado."),
    },
}

METRIC_DEFINITIONS = {
    "coincidencias": "Número de registros; no equivale a vulnerabilidades únicas confirmadas.",
    "coincidencias_totales": "Total de registros en la agrupación; conserva apariciones distintas.",
    "repositorios_afectados": "Número de repositorios distintos con registros de la agrupación.",
    "vulnerabilidades_distintas": "Identificadores distintos tal como aparecen; no se resuelven alias.",
    "proporcion": "Fracción entre 0 y 1; el denominador específico se define en la pregunta.",
    "proporcion_en_repositorio": "Coincidencias de la regla / hallazgos CodeQL del repositorio.",
    "cobertura": "Hallazgos con puntaje / hallazgos observados, por herramienta o repositorio y herramienta.",
    "proporcion_altos": "Hallazgos con puntaje >= umbral / hallazgos con puntaje disponible.",
    "proporcion_altos_herramienta": "Hallazgos altos del repositorio / hallazgos altos de esa herramienta.",
    "proporcion_del_repositorio": "Hallazgos asociados al archivo / hallazgos CodeQL del repositorio; no sumar entre archivos.",
    "cobertura_ubicacion": "Hallazgos con al menos una ubicación / hallazgos CodeQL del repositorio.",
    "proporcion_top_3": "Unión de hallazgos del top 3 de archivos / hallazgos CodeQL del repositorio.",
    "proporcion_componentes": "Registros del ecosistema / todos los registros de componentes cargados.",
    "proporcion_repositorios": "Repositorios con ese ecosistema / repositorios con SBOM válido, incluidos los vacíos.",
    "cobertura_identificacion": "Componentes con clave utilizable / componentes inventariados.",
    "proporcion_afectada": "Componentes con coincidencias / componentes inventariados; null si falta cobertura, correspondencia o denominador.",
    "identidades_afectadas": "Claves distintas de repositorio, ecosistema, nombre y versión con coincidencias.",
    "componentes_con_coincidencias": "Registros del SBOM con alguna coincidencia; múltiples identificadores no multiplican este conteo.",
    "comparacion_completa": "SBOM válido, Grype analyzed, componentes identificables y hallazgos con correspondencia; no acredita cobertura universal de vulnerabilidades.",
    "alguna_coincidencia_grype": "Al menos una aparición tiene coincidencias observadas; false no demuestra ausencia de vulnerabilidades.",
    "hallazgos_ci_observados": "Registros explícitos del lenguaje actions; null cuando no hay resultado de ese lenguaje.",
    "rho_spearman": "Correlación de Pearson entre rangos promedio; asociación monotónica, sin inferencia causal ni prueba de significancia.",
}

DENOMINATORS = {
    1: "proporcion: registros de cada herramienta en todos los repositorios del dataset.",
    2: "proporcion: registros CodeQL globales; proporcion_en_repositorio: registros CodeQL de ese repositorio.",
    3: "En severidades: registros por herramienta y severity_kind. En puntajes: hallazgos puntuados por herramienta, sistema y versión. Las proporciones altas excluyen hallazgos sin puntaje.",
    4: "Se presentan conteos de registros y repositorios distintos; no se suman herramientas ni se deduplican alias.",
    5: "Población restringida a repositorios con ambas herramientas analyzed y conteos con variación.",
    6: "Todos los hallazgos CodeQL del repositorio, incluidos los que carecen de ubicación. El top 3 cuenta la unión de hallazgos.",
    7: "Global: todos los componentes cargados. Presencia: todos los SBOM válidos, incluidos vacíos. Local: componentes del repositorio.",
    8: "Todos los registros de componentes del repositorio; proporción solo con cobertura y correspondencia completas y denominador positivo.",
    9: "Presencia en repositorios distintos; repetición local no aumenta la extensión entre proyectos.",
    10: "Cobertura por repositorio; sin resultado actions el conteo es null, no cero. Frecuencias solo sobre registros observados.",
}


def json_value(value: Any) -> Any:
    """Preserve nulls, booleans and nested lists; never emit NaN or Infinity."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, (str, bool)):
        return value
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        return json_value(value.item())
    raise TypeError(f"Unsupported export value: {type(value).__name__}")


def table(frame: pd.DataFrame, grain: str) -> dict:
    frame = frame.copy()
    if any(name is not None for name in frame.index.names):
        frame = frame.reset_index()
    # Internal join keys are redundant; public identity columns remain available.
    frame = frame.drop(columns=["clave"], errors="ignore")
    if not frame.columns.is_unique:
        raise ValueError("Export tables must have unique column names.")
    return {
        "grain": grain,
        "columns": list(frame.columns),
        "row_count": len(frame),
        "metric_definitions": {name: METRIC_DEFINITIONS[name] for name in frame.columns if name in METRIC_DEFINITIONS},
        "rows": json_value(frame.to_dict(orient="records")),
    }


def question_documentation(notebook_path: Path) -> dict:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    questions = {}
    current = None
    for cell in notebook["cells"]:
        if cell["cell_type"] != "markdown":
            continue
        source = "".join(cell["source"])
        match = re.match(r"## Pregunta (\d+)\. (.+)", source)
        if match:
            current = int(match[1])
            questions[current] = {"title": match[2], "method": [], "limitations": []}
            source = source[match.end():].strip()
        elif source.startswith("## "):
            current = None
        if current is None:
            continue
        if source.startswith("### Limitaciones"):
            questions[current]["limitations"].append(source.removeprefix("### Limitaciones").strip())
        elif source and not source.startswith("### Interpretación"):
            questions[current]["method"].append(source)
    if set(questions) != set(TABLES):
        raise ValueError("The notebook must document questions 1 through 10.")
    return questions


def observations(namespace: dict) -> dict:
    ns = namespace
    relation = (
        f'Entre {len(ns["conteos_relacion"])} repositorios con cobertura completa, '
        f'Spearman ρ = {ns["rho_spearman"]:.3f}: relación {ns["direccion"]} y {ns["intensidad"]}. '
        "La asociación no demuestra causalidad ni significancia estadística."
    )
    return {
        1: ns["observaciones_concentracion"],
        2: ns["observaciones_reglas"],
        3: ns["observaciones"] + ns["observaciones_distribucion"],
        4: ns["observaciones_pregunta_4"] + ns["observaciones_ranking_grype"],
        5: [relation],
        6: ns["observaciones_archivos"],
        7: ns["observaciones_sbom"],
        8: ns["observaciones_componentes"],
        9: ns["observaciones_compartidos"],
        10: [ns["interpretacion_ci"]],
    }


def evidence_statuses(ns: dict) -> dict:
    """Status describes the question's stated population, not repository safety."""
    codeql_partial = ns["repositories"]["codeql_status"].ne("analyzed").any()
    grype_partial = ns["repositories"]["grype_status"].ne("analyzed").any()
    sbom_partial = ns["cobertura_sbom"]["sbom_status"].ne("generated").any()
    partial = {
        1: codeql_partial or grype_partial,
        2: codeql_partial,
        3: codeql_partial or grype_partial or ns["cobertura_puntajes"]["cobertura"].lt(1).any(),
        4: grype_partial,
        5: False,  # The explicitly restricted complete-case population is the target.
        6: codeql_partial or ns["resumen_archivos"]["hallazgos_sin_ubicacion"].gt(0).any(),
        7: sbom_partial or ns["componentes_sbom"]["ecosistema"].eq("Sin clasificar").any(),
        8: (~ns["resumen_componentes"]["comparacion_completa"]).any(),
        9: sbom_partial or any(ns["exclusiones_compartidos"].values()),
        10: ns["cobertura_ci"]["actions_status"].ne("analyzed").any(),
    }
    result = {number: "partial_evidence" if flag else "answered" for number, flag in partial.items()}
    if ns["cobertura_ci"].empty or ns["cobertura_ci"]["actions_status"].eq("not_reported").all():
        result[10] = "insufficient_evidence"
    return result


def evidence_files(ns: dict) -> list[dict]:
    root = Path(ns["REPOSITORY_ROOT"]).resolve()
    paths = {Path(ns[name]).resolve() for name in ("DATASET_PATH", "SBOM_REPORT_PATH", "CODEQL_REPORT_PATH")}
    report_path = Path(ns["SBOM_REPORT_PATH"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for item in report["repositories"]:
        if item.get("status") == "generated":
            filename = item["sbom_path"].replace("\\", "/").rsplit("/", 1)[-1]
            paths.add((report_path.parent / filename).resolve())
    records = []
    for path in sorted(paths):
        if not path.is_relative_to(root):
            raise ValueError("Export evidence must belong to the repository.")
        exists = path.is_file()
        records.append({
            "path": path.relative_to(root).as_posix(),
            "available": exists,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if exists else None,
        })
    return records


def build_export(namespace: dict, notebook_path: Path) -> dict:
    ns = namespace
    documentation = question_documentation(notebook_path)
    statements = observations(ns)
    statuses = evidence_statuses(ns)
    questions = []
    for number, specifications in TABLES.items():
        question_id = f"q{number:02d}"
        docs = documentation[number]
        tables = {name: table(ns[variable], grain) for name, (variable, grain) in specifications.items()}
        metrics = {}
        if number == 3:
            metrics["high_score_threshold"] = ns["HIGH_SCORE_THRESHOLD"]
        elif number == 5:
            metrics = {"rho_spearman": ns["rho_spearman"], "sample_size": len(ns["conteos_relacion"]), "p_value": None}
        elif number == 9:
            metrics["excluded_records"] = ns["exclusiones_compartidos"]
        elif number == 10:
            metrics = {"repositories_analyzed": ns["ci_completos"], "repositories_not_reported": ns["ci_sin_evidencia"]}
        questions.append({
            "id": question_id,
            "title": docs["title"],
            "status": statuses[number],
            "method_and_definitions_markdown": "\n\n".join(docs["method"]),
            "population_and_denominators": DENOMINATORS[number],
            "limitations_markdown": "\n\n".join(docs["limitations"]),
            "metrics": json_value(metrics),
            "observations": [
                {"id": f"{question_id}-o{index:02d}", "text_markdown": value,
                 "evidence_tables": list(tables)}
                for index, value in enumerate(statements[number], 1)
            ],
            "tables": tables,
        })
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    source = [{"cell_type": cell["cell_type"], "source": cell["source"]} for cell in notebook["cells"]]
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "organization": ns["dataset"]["organization"],
        "clone_run": ns["dataset"]["clone_run"],
        "summary": {
            "repositories": len(ns["repositories"]),
            "finding_records": len(ns["findings"]),
            "component_records": len(ns["componentes_sbom"]),
            "questions": len(questions),
            "scope": "Patrones descriptivos de concentración, repetición y asociación; no confirma explotabilidad ni causalidad.",
        },
        "conventions": {
            "null": "Dato ausente o métrica no definida; nunca equivale automáticamente a cero.",
            "proportions": "Fracciones entre 0 y 1, no porcentajes de 0 a 100.",
            "statuses": {
                "answered": "La evidencia permite responder para la población declarada, con las limitaciones documentadas.",
                "partial_evidence": "Existen resultados, pero hay cobertura, identificación o puntuación incompleta.",
                "insufficient_evidence": "No se dispone de evidencia suficiente para responder la pregunta.",
            },
            "tools": "CodeQL y Grype mantienen escalas y conteos separados.",
        },
        "provenance": {
            "notebook": notebook_path.resolve().relative_to(Path(ns["REPOSITORY_ROOT"]).resolve()).as_posix(),
            "notebook_source_sha256": hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            "exporter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "python": platform.python_version(),
            "packages": {name: version(name) for name in ("pandas", "matplotlib", "nbformat")},
            "evidence": evidence_files(ns),
        },
        "coverage": {
            "tools": table(ns["coverage"], "Etapa y estado; número de repositorios."),
            "sbom": table(ns["cobertura_sbom"], "Repositorio y estado del inventario."),
            "ci": table(ns["cobertura_ci"], "Repositorio y estado específico de Actions."),
        },
        "questions": questions,
    }
    validate_export(result)
    return result


def validate_export(payload: dict) -> None:
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported export schema version.")
    if [question["id"] for question in payload["questions"]] != [f"q{n:02d}" for n in range(1, 11)]:
        raise ValueError("The export must contain each research question exactly once.")
    for question in payload["questions"]:
        if question["status"] not in payload["conventions"]["statuses"]:
            raise ValueError("Unknown evidence status.")
        if not question["observations"] or not question["limitations_markdown"]:
            raise ValueError("Every question requires observations and limitations.")
        for observation in question["observations"]:
            if not set(observation["evidence_tables"]).issubset(question["tables"]):
                raise ValueError("An observation references a missing table.")
        for exported_table in question["tables"].values():
            if len(exported_table["rows"]) != exported_table["row_count"]:
                raise ValueError("Table row count mismatch.")
            if any(set(row) != set(exported_table["columns"]) for row in exported_table["rows"]):
                raise ValueError("Table columns and row fields differ.")
    json.dumps(payload, ensure_ascii=False, allow_nan=False)


def export_analysis(namespace: dict, notebook_path: Path, output_path: Path) -> Path:
    payload = build_export(namespace, notebook_path)
    content = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=output_path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        os.replace(temporary, output_path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return output_path
