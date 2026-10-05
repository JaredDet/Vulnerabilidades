import { Component, computed, input } from '@angular/core';

import { AnalysisQuestion, AnalysisValue } from '../../interfaces/analysis';
import { Chart, ChartSeries } from '../chart/chart';

function text(value: AnalysisValue | undefined): string {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return '';
}

@Component({
  imports: [Chart],
  selector: 'app-packages',
  styleUrl: './packages.css',
  templateUrl: './packages.html',
})
export class Packages {
  readonly question = input.required<AnalysisQuestion>();

  readonly chart = computed(() => {
    const rows = this.question().tables['paquetes_compartidos']?.rows ?? [];
    const series: ChartSeries[] = [
      {
        label: 'coincidencias_totales',
        data: rows.map((row) => (typeof row['coincidencias_totales'] === 'number' ? row['coincidencias_totales'] : null)),
      },
    ];
    return {
      labels: rows.map((row) => text(row['package'])),
      series,
    };
  });
}
