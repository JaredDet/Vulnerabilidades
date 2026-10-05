import { Component, computed, input } from '@angular/core';

import { AnalysisQuestion, AnalysisValue } from '../../interfaces/analysis';
import { Chart, ChartSeries } from '../chart/chart';
import { DataTable, DataTableColumn } from '../data-table/data-table';

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
  imports: [Chart, DataTable],
  selector: 'app-shared',
  styleUrl: './shared.css',
  templateUrl: './shared.html',
})
export class Shared {
  readonly question = input.required<AnalysisQuestion>();
  readonly nullText = input('');

  readonly versions = computed(() => this.question().tables['versiones_compartidas']);

  readonly versionColumns = computed<DataTableColumn[]>(() =>
    (this.versions()?.columns ?? []).map((key) => ({ key, filter: key === 'ecosistema' })),
  );

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

}
