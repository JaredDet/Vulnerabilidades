"""Validate and execute the analysis notebook using its committed evidence."""

from pathlib import Path
import os

import matplotlib
import nbformat
from IPython.utils.capture import capture_output

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    notebook = nbformat.read(project / "notebooks/analyzer.ipynb", as_version=4)
    nbformat.validate(notebook)
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
    print(f"Validated and executed {executed} code cells.")


if __name__ == "__main__":
    main()
