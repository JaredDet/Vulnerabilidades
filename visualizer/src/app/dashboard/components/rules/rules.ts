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

function bar(rows: Array<Record<string, AnalysisValue>>, labelKey: string, valueKey: string): {
  labels: string[];
  series: ChartSeries[];
} {
  return {
    labels: rows.map((row) => text(row[labelKey])),
    series: [
      {
        label: valueKey,
        data: rows.map((row) => (typeof row[valueKey] === 'number' ? row[valueKey] : null)),
      },
    ],
  };
}

@Component({
  imports: [Chart, DataTable],
  selector: 'app-rules',
  styleUrl: './rules.css',
  templateUrl: './rules.html',
})
export class Rules {
  readonly question = input.required<AnalysisQuestion>();
  readonly nullText = input('');

  readonly ruleColumns: DataTableColumn[] = [
    { key: 'vulnerability_id' },
    { key: 'coincidencias' },
    { key: 'repositorios', filter: true },
    { key: 'proporcion' },
    { key: 'ejemplo_mensaje' },
  ];

  readonly ruleSort: DataTableSort = { key: 'coincidencias', direction: 'desc' };

  readonly frequency = computed(() =>
    bar(this.question().tables['reglas_globales']?.rows ?? [], 'vulnerability_id', 'coincidencias'),
  );

  readonly sharedRules = computed(() =>
    bar(this.question().tables['reglas_compartidas']?.rows ?? [], 'vulnerability_id', 'repositorios_afectados'),
  );

  readonly ruleRows = computed(() => this.question().tables['reglas_globales']?.rows ?? []);
}
