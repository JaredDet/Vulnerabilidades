import { Component, computed, input } from '@angular/core';

import { AnalysisQuestion, AnalysisValue } from '../../interfaces/analysis';
import { Chart, ChartSeries } from '../chart/chart';
import { DataTable, DataTableColumn, DataTableSort } from '../data-table/data-table';

function text(value: AnalysisValue | undefined): string {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return '';
}

function chartFor(
  rows: Array<Record<string, AnalysisValue>>,
  valueKey: string,
): { labels: string[]; series: ChartSeries[] } {
  const numeric = rows.filter((row) => typeof row[valueKey] === 'number');
  return {
    labels: numeric.map((row) => text(row['repository'])),
    series: [
      {
        label: valueKey,
        data: numeric.map((row) => (typeof row[valueKey] === 'number' ? row[valueKey] : null)),
      },
    ],
  };
}

@Component({
  imports: [Chart, DataTable],
  selector: 'app-exposure',
  styleUrl: './exposure.css',
  templateUrl: './exposure.html',
})
export class Exposure {
  readonly question = input.required<AnalysisQuestion>();
  readonly nullText = input('');

  readonly exposureColumns: DataTableColumn[] = [
    { key: 'repository' },
    { key: 'componentes_totales' },
    { key: 'componentes_con_coincidencias' },
    { key: 'proporcion_afectada' },
  ];

  readonly exposureSort: DataTableSort = { key: 'proporcion_afectada', direction: 'desc' };

  readonly exposureRows = computed(() =>
    (this.question().tables['componentes_por_repositorio']?.rows ?? []).filter(
      (row) => row['proporcion_afectada'] !== null && row['proporcion_afectada'] !== undefined,
    ),
  );

  readonly charts = computed(() => {
    const rows = this.question().tables['componentes_por_repositorio']?.rows ?? [];
    return [
      chartFor(rows, 'componentes_totales'),
      chartFor(rows, 'proporcion_afectada'),
    ];
  });
}
