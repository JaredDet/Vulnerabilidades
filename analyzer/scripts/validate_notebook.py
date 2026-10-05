"""Validate and execute the analysis notebook using its committed evidence."""

from pathlib import Path
import os
import re

import matplotlib
import nbformat
from IPython.utils.capture import capture_output

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def validate_markdown_answers(notebook: nbformat.NotebookNode) -> int:
    """Require a non-empty Markdown interpretation for each research question."""
    answers: dict[int, list[str]] = {}
    current_question: int | None = None
    in_interpretation = False

    for cell in notebook.cells:
        if cell.cell_type != "markdown":
            continue
        source = cell.source.strip()
        question = re.match(r"## Pregunta (\d+)\.", source)
        if question:
            current_question = int(question.group(1))
            answers.setdefault(current_question, [])
            in_interpretation = False
        if current_question is None:
            continue

        if re.match(r"### Interpretación(?:\s|$)", source):
            in_interpretation = True
            body = re.sub(r"^### Interpretación[^\n]*\n?", "", source).strip()
            if body:
                answers[current_question].append(body)
        elif source.startswith("### "):
            in_interpretation = False
        elif in_interpretation and source:
            answers[current_question].append(source)

    expected = set(range(1, 10))
    missing_questions = expected - answers.keys()
    missing_answers = {number for number in expected if not answers.get(number)}
    if missing_questions or missing_answers:
        details = []
        if missing_questions:
            details.append(f"faltan preguntas {sorted(missing_questions)}")
        if missing_answers:
            details.append(f"faltan interpretaciones Markdown para {sorted(missing_answers)}")
        raise ValueError("El notebook no cumple su contenido de investigación: " + "; ".join(details))
    return sum(len(items) for items in answers.values())


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    notebook = nbformat.read(project / "notebooks/analyzer.ipynb", as_version=4)
    nbformat.validate(notebook)
    markdown_answers = validate_markdown_answers(notebook)
    namespace = {"__name__": "__main__"}
    previous_directory = Path.cwd()
    executed = 0
    try:
        os.chdir(project)
        for index, cell in enumerate(notebook.cells):
            if cell.cell_type != "code":
                continue
            with capture_output():
                exec(compile(cell.source, f"notebook_cell_{index}", "exec"), namespace)
            plt.close("all")
            executed += 1
    finally:
        plt.close("all")
        os.chdir(previous_directory)
    print(
        f"Validated {markdown_answers} Markdown answers and executed "
        f"{executed} code cells."
    )


if __name__ == "__main__":
    main()
