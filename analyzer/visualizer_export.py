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


SCHEMA_VERSION = "1.1"

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
}

# Explicitly connect each plot to its quantitative table and visual encodings.
# The Visualizer can render these datasets without reverse engineering notebook code.
VISUALIZATIONS = {
    1: [
        {"id": "concentracion_hallazgos", "type": "bar_horizontal", "title": "Concentración de hallazgos por repositorio", "table": "concentracion", "value_format": "percent", "encoding": {"x": "proporcion", "y": "repository", "series": "tool", "tooltip": ["coincidencias", "status"]}},
    ],
    2: [
        {"id": "reglas_frecuentes", "type": "bar_horizontal", "title": "Reglas de CodeQL más frecuentes", "table": "reglas_globales", "encoding": {"x": "coincidencias", "y": "vulnerability_id", "tooltip": ["repositorios", "proporcion"]}},
        {"id": "reglas_por_repositorio", "type": "heatmap", "title": "Proporción de reglas por repositorio", "table": "reglas_por_repositorio", "encoding": {"x": "vulnerability_id", "y": "repository", "value": "proporcion_en_repositorio"}},
    ],
    3: [
        {"id": "hallazgos_altos", "type": "bar_horizontal", "title": "Hallazgos con puntaje alto por repositorio", "table": "puntajes_por_repositorio", "encoding": {"x": "hallazgos_altos", "y": "repository", "series": "tool", "tooltip": ["hallazgos_puntuados", "cobertura", "proporcion_altos"]}},
        {"id": "distribucion_severidades", "type": "bar", "title": "Severidades observadas", "table": "severidades", "encoding": {"x": "severity", "y": "coincidencias", "series": "tool"}},
    ],
    4: [
        {"id": "paquetes_frecuentes", "type": "bar_horizontal", "title": "Paquetes con más coincidencias de Grype", "table": "paquetes", "encoding": {"x": "coincidencias_totales", "y": "package", "tooltip": ["package_type", "repositorios_afectados"]}},
        {"id": "identificadores_frecuentes", "type": "bar_horizontal", "title": "Identificadores de Grype más frecuentes", "table": "identificadores", "encoding": {"x": "coincidencias_totales", "y": "vulnerability_id", "tooltip": ["repositorios_afectados", "paquetes_afectados"]}},
        {"id": "paquetes_compartidos", "type": "bar_horizontal", "title": "Paquetes vulnerables compartidos", "table": "paquetes_compartidos", "encoding": {"x": "repositorios_afectados", "y": "package", "tooltip": ["coincidencias_totales", "vulnerabilidades_distintas"]}},
        {"id": "identificadores_compartidos", "type": "bar_horizontal", "title": "Vulnerabilidades compartidas", "table": "identificadores_compartidos", "encoding": {"x": "repositorios_afectados", "y": "vulnerability_id", "tooltip": ["coincidencias_totales", "paquetes_afectados"]}},
    ],
    5: [
        {"id": "relacion_conteos", "type": "scatter", "title": "Conteos por repositorio: CodeQL y Grype", "table": "relacion_conteos", "encoding": {"x": "hallazgos_codeql", "y": "hallazgos_grype", "label": "repository", "tooltip": ["codeql_status", "grype_status"]}},
    ],
    6: [
        {"id": "hallazgos_por_archivo", "type": "bar_horizontal_facets", "title": "Archivos con más hallazgos por repositorio", "table": "top_archivos", "encoding": {"x": "hallazgos", "y": "archivo", "facet": "repository", "tooltip": ["reglas_distintas", "proporcion_del_repositorio"]}},
    ],
    7: [
        {"id": "componentes_por_ecosistema", "type": "bar_horizontal", "title": "Componentes por ecosistema", "table": "ecosistemas", "encoding": {"x": "componentes", "y": "ecosistema", "tooltip": ["repositorios", "proporcion_componentes"]}},
        {"id": "composicion_por_repositorio", "type": "bar_stacked", "title": "Composición de ecosistemas por repositorio", "table": "ecosistemas_por_repositorio", "value_format": "percent", "encoding": {"x": "proporcion", "y": "repository", "series": "ecosistema", "tooltip": ["componentes"]}},
    ],
    8: [
        {"id": "inventario_por_repositorio", "type": "bar_horizontal", "title": "Componentes inventariados por repositorio", "table": "componentes_por_repositorio", "encoding": {"x": "componentes_totales", "y": "repository", "tooltip": ["sbom_status", "componentes_identificables"]}},
        {"id": "proporcion_afectada", "type": "bar_horizontal", "title": "Proporción de componentes con coincidencias", "table": "componentes_por_repositorio", "value_format": "percent", "encoding": {"x": "proporcion_afectada", "y": "repository", "tooltip": ["componentes_con_coincidencias", "componentes_totales", "comparacion_completa"]}},
    ],
    9: [
        {"id": "paquetes_sbom_compartidos", "type": "bar_horizontal", "title": "Paquetes compartidos entre repositorios", "table": "paquetes_compartidos", "encoding": {"x": "repositorios", "y": "nombre_normalizado", "series": "ecosistema", "tooltip": ["registros", "versiones_observadas", "alguna_coincidencia_grype"]}},
        {"id": "versiones_sbom_compartidas", "type": "bar_horizontal", "title": "Versiones compartidas entre repositorios", "table": "versiones_compartidas", "encoding": {"x": "repositorios", "y": "version_identificada", "series": "ecosistema", "tooltip": ["nombre_normalizado", "registros", "alguna_coincidencia_grype"]}},
    ],
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


def export_table_data(namespace: dict, variable: str) -> pd.DataFrame:
    """Resolve table inputs, deriving simple summaries from current notebook data."""
    if variable == "distribucion_severidades":
        findings = namespace["findings"]
        return (
            findings.dropna(subset=["severity"])
            .groupby(["tool", "severity_kind", "severity"], dropna=False)
            .size().rename("coincidencias").reset_index()
        )
    if variable == "distribucion_puntajes":
        return namespace["scores"].copy()
    return namespace[variable]


def question_documentation(notebook_path: Path) -> dict:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    questions = {}
    current = None
    in_interpretation = False
    for cell in notebook["cells"]:
        if cell["cell_type"] != "markdown":
            continue
        source = "".join(cell["source"])
        match = re.match(r"## Pregunta (\d+)\. (.+)", source)
        if match:
            current = int(match[1])
            questions[current] = {"title": match[2], "method": [], "limitations": [], "interpretations": []}
            in_interpretation = False
            source = source[match.end():].strip()
        elif source.startswith("## "):
            current = None
            in_interpretation = False
        if current is None:
            continue
        if source.startswith("### Limitaciones"):
            in_interpretation = False
            questions[current]["limitations"].append(source.removeprefix("### Limitaciones").strip())
        elif source.startswith("### Interpretación"):
            in_interpretation = True
            questions[current]["interpretations"].append(
                source.removeprefix("### Interpretación").strip()
            )
        elif source.startswith("### "):
            in_interpretation = False
            continue
        elif source:
            if in_interpretation:
                if questions[current]["interpretations"][-1]:
                    questions[current]["interpretations"][-1] += "\n\n" + source
                else:
                    questions[current]["interpretations"][-1] = source
            elif questions[current]["interpretations"] and not questions[current]["limitations"]:
                questions[current]["interpretations"][-1] += "\n\n" + source
            else:
                questions[current]["method"].append(source)
    if set(questions) != set(TABLES):
        raise ValueError("The notebook must document questions 1 through 9.")
    return questions


def observations(documentation: dict) -> dict:
    return {number: docs["interpretations"] for number, docs in documentation.items()}


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
    }
    result = {number: "partial_evidence" if flag else "answered" for number, flag in partial.items()}
    return result


def evidence_files(ns: dict) -> list[dict]:
    root = Path(ns["REPOSITORY_ROOT"]).resolve()
    paths = {Path(ns[name]).resolve() for name in ("DATASET_PATH", "SBOM_REPORT_PATH")}
    if ns.get("CODEQL_REPORT_PATH"):
        paths.add(Path(ns["CODEQL_REPORT_PATH"]).resolve())
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
    statements = observations(documentation)
    statuses = evidence_statuses(ns)
    questions = []
    for number, specifications in TABLES.items():
        question_id = f"q{number:02d}"
        docs = documentation[number]
        tables = {name: table(export_table_data(ns, variable), grain) for name, (variable, grain) in specifications.items()}
        metrics = {}
        if number == 3:
            metrics["high_score_threshold"] = ns["HIGH_SCORE_THRESHOLD"]
        elif number == 5:
            metrics = {"rho_spearman": ns["rho_spearman"], "sample_size": len(ns["conteos_relacion"]), "p_value": None}
        elif number == 9:
            metrics["excluded_records"] = ns["exclusiones_compartidos"]
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
                 "evidence_tables": list(tables),
                 "visualization_ids": observation_visualization_ids(number, index)}
                for index, value in enumerate(statements[number], 1)
            ],
            "visualizations": [
                {
                    **{key: value for key, value in visualization.items() if key != "table"},
                    "data_table": visualization["table"],
                }
                for visualization in VISUALIZATIONS[number]
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
        },
        "questions": questions,
    }
    validate_export(result)
    return result


def validate_export(payload: dict) -> None:
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported export schema version.")
    if [question["id"] for question in payload["questions"]] != [f"q{n:02d}" for n in range(1, 10)]:
        raise ValueError("The export must contain each research question exactly once.")
    for question in payload["questions"]:
        if question["status"] not in payload["conventions"]["statuses"]:
            raise ValueError("Unknown evidence status.")
        if not question["observations"] or not question["limitations_markdown"]:
            raise ValueError("Every question requires observations and limitations.")
        for observation in question["observations"]:
            if not set(observation["evidence_tables"]).issubset(question["tables"]):
                raise ValueError("An observation references a missing table.")
            visualization_ids = {item["id"] for item in question["visualizations"]}
            if not set(observation["visualization_ids"]).issubset(visualization_ids):
                raise ValueError("An observation references a missing visualization.")
        for visualization in question["visualizations"]:
            table_name = visualization["data_table"]
            if table_name not in question["tables"]:
                raise ValueError("A visualization references a missing table.")
            columns = set(question["tables"][table_name]["columns"])
            fields = {
                value for value in visualization["encoding"].values()
                if isinstance(value, str)
            }
            fields.update(
                field
                for value in visualization["encoding"].values()
                if isinstance(value, list)
                for field in value
            )
            if not fields.issubset(columns):
                raise ValueError("A visualization encoding references a missing column.")
        for exported_table in question["tables"].values():
            if len(exported_table["rows"]) != exported_table["row_count"]:
                raise ValueError("Table row count mismatch.")
            if any(set(row) != set(exported_table["columns"]) for row in exported_table["rows"]):
                raise ValueError("Table columns and row fields differ.")
    json.dumps(payload, ensure_ascii=False, allow_nan=False)


def observation_visualization_ids(question_number: int, observation_number: int) -> list[str]:
    """Link qualitative findings to the chart data that can substantiate them."""
    if question_number == 4 and observation_number == 1:
        indexes = (0, 1)
    elif question_number == 4 and observation_number == 2:
        indexes = (2, 3)
    else:
        indexes = tuple(range(len(VISUALIZATIONS[question_number])))
    return [VISUALIZATIONS[question_number][index]["id"] for index in indexes]


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
