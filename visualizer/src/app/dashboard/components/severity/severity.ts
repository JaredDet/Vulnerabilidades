import { Component, computed, input } from '@angular/core';

import { AnalysisQuestion, AnalysisValue } from '../../interfaces/analysis';
import { Chart, ChartSeries, formatAnalysisNumber } from '../chart/chart';

function text(value: AnalysisValue | undefined): string {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return '';
}


const SEVERITY_ORDER = ['critical', 'error', 'high', 'warning', 'medium', 'low', 'note', 'negligible', 'unknown', 'none'];

const SEVERITY_COLOR: Record<string, string> = {
  critical: 'rgba(153, 27, 27, 0.9)',
  error: 'rgba(220, 38, 38, 0.9)',
  high: 'rgba(234, 88, 12, 0.9)',
  warning: 'rgba(217, 119, 6, 0.9)',
  medium: 'rgba(202, 138, 4, 0.9)',
  low: 'rgba(37, 99, 235, 0.85)',
  note: 'rgba(8, 145, 178, 0.85)',
  negligible: 'rgba(100, 116, 139, 0.85)',
  unknown: 'rgba(148, 163, 184, 0.85)',
  none: 'rgba(203, 213, 225, 0.9)',
};

function severityRank(label: string): number {
  const index = SEVERITY_ORDER.indexOf(label.toLowerCase());
  return index === -1 ? SEVERITY_ORDER.length : index;
}

function severityColor(label: string): string {
  return SEVERITY_COLOR[label.toLowerCase()] ?? 'rgba(71, 85, 105, 0.8)';
}

@Component({
  imports: [Chart],
  selector: 'app-severity',
  styleUrl: './severity.css',
  templateUrl: './severity.html',
})
export class Severity {
  readonly question = input.required<AnalysisQuestion>();

  readonly stats = computed(() => {
    const coverage = this.question().tables['cobertura_puntajes']?.rows ?? [];
    const severities = this.question().tables['severidades']?.rows ?? [];
    const coverageStats = coverage.map((row) => ({
      value: typeof row['proporcion_altos'] === 'number' ? formatAnalysisNumber(row['proporcion_altos'], 'proporcion_altos') : '',
      label: text(row['tool']),
    }));
    const tools = [...new Set(severities.map((row) => text(row['tool'])).filter((tool) => tool !== ''))];
    const top = tools.map((tool) => {
      const rows = severities.filter((row) => text(row['tool']) === tool);
      const total = rows.reduce(
        (sum, row) => sum + (typeof row['coincidencias'] === 'number' ? row['coincidencias'] : 0),
        0,
      );
      const best = rows.reduce((current, row) => {
        const count = typeof row['coincidencias'] === 'number' ? row['coincidencias'] : -1;
        const currentCount = typeof current['coincidencias'] === 'number' ? current['coincidencias'] : -1;
        return count > currentCount ? row : current;
      });
      return {
        value:
          total > 0 && typeof best['coincidencias'] === 'number'
            ? formatAnalysisNumber(best['coincidencias'] / total, 'proporcion')
            : '',
        label: text(best['severity']),
      };
    });
    return [...coverageStats, ...top];
  });

  readonly severityCharts = computed(() => {
    const rows = this.question().tables['severidades']?.rows ?? [];
    const tools = [...new Set(rows.map((row) => text(row['tool'])).filter((tool) => tool !== ''))];
    return tools.map((tool) => {
      const matching = rows
        .filter((row) => text(row['tool']) === tool)
        .sort((left, right) => severityRank(text(left['severity'])) - severityRank(text(right['severity'])));
      const labels = matching.map((row) => text(row['severity']));
      const series: ChartSeries[] = [
        {
          label: 'hallazgos',
          data: matching.map((row) => (typeof row['coincidencias'] === 'number' ? row['coincidencias'] : null)),
          colors: labels.map((label) => severityColor(label)),
        },
      ];
      return { tool, labels, series };
    });
  });

  readonly scoreChart = computed(() => {
    const rows = this.question().tables['puntajes_por_repositorio']?.rows ?? [];
    const repositories = [...new Set(rows.map((row) => text(row['repository'])).filter((repository) => repository !== ''))];
    const tools = [...new Set(rows.map((row) => text(row['tool'])).filter((tool) => tool !== ''))];
    const series: ChartSeries[] = tools.map((tool) => ({
      label: tool,
      data: repositories.map((repository) => {
        const row = rows.find((item) => text(item['repository']) === repository && text(item['tool']) === tool);
        return row && typeof row['hallazgos_altos'] === 'number' ? row['hallazgos_altos'] : null;
      }),
    }));
    return { labels: repositories, series };
  });
}
