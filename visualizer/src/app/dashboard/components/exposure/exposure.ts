import { Component, computed, input } from '@angular/core';

import { AnalysisQuestion, AnalysisValue } from '../../interfaces/analysis';
import { Chart, ChartSeries } from '../chart/chart';

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
  imports: [Chart],
  selector: 'app-exposure',
  styleUrl: './exposure.css',
  templateUrl: './exposure.html',
})
export class Exposure {
  readonly question = input.required<AnalysisQuestion>();

  readonly charts = computed(() => {
    const rows = this.question().tables['componentes_por_repositorio']?.rows ?? [];
    return [
      chartFor(rows, 'componentes_totales'),
      chartFor(rows, 'proporcion_afectada'),
    ];
  });
}
