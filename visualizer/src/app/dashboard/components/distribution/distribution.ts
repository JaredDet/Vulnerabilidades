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
  selector: 'app-distribution',
  styleUrl: './distribution.css',
  templateUrl: './distribution.html',
})
export class Distribution {
  readonly question = input.required<AnalysisQuestion>();

  readonly charts = computed(() => {
    const rows = this.question().tables['concentracion']?.rows ?? [];
    const tools = [...new Set(rows.map((row) => text(row['tool'])).filter((tool) => tool !== ''))];
    return tools.map((tool) => {
      const matching = rows.filter((row) => text(row['tool']) === tool);
      const series: ChartSeries[] = [
        {
          label: 'proporcion',
          data: matching.map((row) => (typeof row['proporcion'] === 'number' ? row['proporcion'] : null)),
        },
      ];
      return {
        tool,
        labels: matching.map((row) => text(row['repository'])),
        series,
      };
    });
  });
}
