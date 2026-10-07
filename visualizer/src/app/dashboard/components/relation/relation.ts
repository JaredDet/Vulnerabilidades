import { Component, computed, input } from '@angular/core';

import { AnalysisQuestion, AnalysisValue } from '../../interfaces/analysis';
import { Chart, ChartSeries, formatAnalysisNumber } from '../chart/chart';

function text(value: AnalysisValue | undefined): string {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return '';
}

@Component({
  imports: [Chart],
  selector: 'app-relation',
  styleUrl: './relation.css',
  templateUrl: './relation.html',
})
export class Relation {
  readonly question = input.required<AnalysisQuestion>();
  readonly nullText = input('');

  readonly stats = computed(() => {
    const metrics = this.question().metrics;
    return ['rho_spearman', 'p_value'].map((key) => {
      const value = metrics[key];
      return {
        label: key,
        value:
          typeof value === 'number'
            ? formatAnalysisNumber(value, key)
            : value === null || value === undefined
              ? this.nullText()
              : String(value),
      };
    });
  });

  readonly chart = computed(() => {
    const rows = this.question().tables['relacion_conteos']?.rows ?? [];
    const series: ChartSeries[] = ['hallazgos_codeql', 'hallazgos_grype'].map((key) => ({
      label: key,
      data: rows.map((row) => (typeof row[key] === 'number' ? row[key] : null)),
    }));
    return {
      labels: rows.map((row) => text(row['repository'])),
      series,
    };
  });
}
