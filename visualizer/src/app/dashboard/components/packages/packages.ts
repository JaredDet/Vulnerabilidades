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

@Component({
  imports: [Chart, DataTable],
  selector: 'app-packages',
  styleUrl: './packages.css',
  templateUrl: './packages.html',
})
export class Packages {
  readonly question = input.required<AnalysisQuestion>();
  readonly nullText = input('');

  readonly packageColumns: DataTableColumn[] = [
    { key: 'package' },
    { key: 'package_type', filter: true },
    { key: 'versiones_observadas' },
    { key: 'vulnerabilidades_distintas' },
    { key: 'repositorios_afectados' },
  ];

  readonly packageSort: DataTableSort = { key: 'repositorios_afectados', direction: 'desc' };

  readonly identifierColumns: DataTableColumn[] = [
    { key: 'vulnerability_id' },
    { key: 'paquetes_afectados' },
    { key: 'repositorios_afectados' },
    { key: 'coincidencias_totales' },
    { key: 'severidades', filter: true },
  ];

  readonly identifierSort: DataTableSort = { key: 'coincidencias_totales', direction: 'desc' };

  readonly packageRows = computed(() => this.question().tables['paquetes_compartidos']?.rows ?? []);

  readonly identifierRows = computed(() => this.question().tables['identificadores_compartidos']?.rows ?? []);

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
