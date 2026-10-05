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
  selector: 'app-ecosystems',
  styleUrl: './ecosystems.css',
  templateUrl: './ecosystems.html',
})
export class Ecosystems {
  readonly question = input.required<AnalysisQuestion>();
  readonly nullText = input('');

  readonly ecosystems = computed(() => this.question().tables['ecosistemas']);

  readonly doughnut = computed(() => {
    const rows = this.ecosystems()?.rows ?? [];
    const series: ChartSeries[] = [
      {
        label: 'componentes',
        data: rows.map((row) => (typeof row['componentes'] === 'number' ? row['componentes'] : null)),
      },
    ];
    return {
      labels: rows.map((row) => text(row['ecosistema'])),
      series,
    };
  });

  readonly stacked = computed(() => {
    const rows = this.question().tables['ecosistemas_por_repositorio']?.rows ?? [];
    const repositories = [...new Set(rows.map((row) => text(row['repository'])).filter((repository) => repository !== ''))];
    const ecosystems = [...new Set(rows.map((row) => text(row['ecosistema'])).filter((ecosistema) => ecosistema !== ''))];
    const series: ChartSeries[] = ecosystems.map((ecosistema) => ({
      label: ecosistema,
      data: repositories.map((repository) => {
        const row = rows.find(
          (item) => text(item['repository']) === repository && text(item['ecosistema']) === ecosistema,
        );
        return row && typeof row['componentes'] === 'number' ? row['componentes'] : null;
      }),
    }));
    return { labels: repositories, series };
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
