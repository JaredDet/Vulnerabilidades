import { Component, computed, input } from '@angular/core';

import { AnalysisQuestion, AnalysisTable, AnalysisValue } from '../../interfaces/analysis';
import { Chart, ChartSeries, formatAnalysisNumber } from '../chart/chart';

function text(value: AnalysisValue | undefined): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => text(item)).join(', ');
  }
  return '';
}

@Component({
  imports: [Chart],
  selector: 'app-shared',
  styleUrl: './shared.css',
  templateUrl: './shared.html',
})
export class Shared {
  readonly question = input.required<AnalysisQuestion>();
  readonly nullText = input('');

  readonly versions = computed(() => this.question().tables['versiones_compartidas']);

  readonly chart = computed(() => {
    const rows = this.question().tables['paquetes_compartidos']?.rows ?? [];
    const series: ChartSeries[] = [
      {
        label: 'repositorios',
        data: rows.map((row) => (typeof row['repositorios'] === 'number' ? row['repositorios'] : null)),
      },
    ];
    return {
      labels: rows.map((row) => [text(row['ecosistema']), text(row['nombre_normalizado'])].filter((part) => part !== '').join(' ')),
      series,
    };
  });

  cell(table: AnalysisTable, row: Record<string, AnalysisValue>, column: string): string {
    const value = row[column];
    if (value === null || value === undefined) {
      return this.nullText();
    }
    if (typeof value === 'number') {
      return formatAnalysisNumber(value, column);
    }
    return text(value);
  }
}
