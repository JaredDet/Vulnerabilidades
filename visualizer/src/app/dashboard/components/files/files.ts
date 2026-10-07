import { Component, computed, effect, input, signal } from '@angular/core';

import { AnalysisQuestion, AnalysisValue } from '../../interfaces/analysis';
import { Chart, ChartSeries } from '../chart/chart';
import { DataTable, DataTableColumn, DataTableSort } from '../data-table/data-table';

function text(value: AnalysisValue | undefined): string {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return '';
}

@Component({
  imports: [Chart, DataTable],
  selector: 'app-files',
  styleUrl: './files.css',
  templateUrl: './files.html',
})
export class Files {
  readonly question = input.required<AnalysisQuestion>();
  readonly nullText = input('');
  readonly selected = signal<string | null>(null);

  readonly fileColumns: DataTableColumn[] = [
    { key: 'archivo' },
    { key: 'hallazgos' },
    { key: 'reglas_distintas' },
    { key: 'proporcion_del_repositorio' },
  ];

  readonly fileSort: DataTableSort = { key: 'hallazgos', direction: 'desc' };

  readonly repositories = computed(() => {
    const rows = this.question().tables['top_archivos']?.rows ?? [];
    return [...new Set(rows.map((row) => text(row['repository'])).filter((repository) => repository !== ''))];
  });

  readonly fileRows = computed(() => {
    const selected = this.selected();
    return (this.question().tables['top_archivos']?.rows ?? []).filter(
      (row) => text(row['repository']) === selected,
    );
  });

  readonly chart = computed(() => {
    const rows = this.fileRows();
    const series: ChartSeries[] = [
      {
        label: 'hallazgos',
        data: rows.map((row) => (typeof row['hallazgos'] === 'number' ? row['hallazgos'] : null)),
      },
    ];
    return {
      labels: rows.map((row) => text(row['archivo'])),
      series,
    };
  });

  constructor() {
    effect(() => {
      const repositories = this.repositories();
      if (this.selected() === null && repositories.length > 0) {
        this.selected.set(repositories[0]);
      }
    });
  }

  select(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.selected.set(value);
  }
}
