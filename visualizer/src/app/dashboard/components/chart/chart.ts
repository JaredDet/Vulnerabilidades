import { isPlatformBrowser } from '@angular/common';
import {
  Component,
  ElementRef,
  PLATFORM_ID,
  afterNextRender,
  effect,
  inject,
  input,
  viewChild,
} from '@angular/core';
import { Chart as ChartJs, ChartConfiguration, registerables } from 'chart.js';

ChartJs.register(...registerables);

export interface ChartSeries {
  label: string;
  data: Array<number | null>;
  colors?: string[];
}

export function formatAnalysisNumber(value: number, key = ''): string {
  const percent = key.includes('proporcion');
  const shown = percent ? value * 100 : value;
  const rounded = Number.isInteger(shown) ? String(shown) : shown.toFixed(2).replace(/\.?0+$/, '');
  return percent ? `${rounded}%` : rounded;
}

const COLORS = [
  'rgba(37, 99, 235, 0.8)',
  'rgba(217, 119, 6, 0.8)',
  'rgba(71, 85, 105, 0.8)',
];

@Component({
  selector: 'app-chart',
  styleUrl: './chart.css',
  templateUrl: './chart.html',
})
export class Chart {
  readonly labels = input<string[]>([]);
  readonly series = input<ChartSeries[]>([]);
  readonly kind = input<'bar' | 'doughnut'>('bar');
  readonly horizontal = input(false);
  readonly stacked = input(false);
  readonly title = input('');

  private readonly canvas = viewChild<ElementRef<HTMLCanvasElement>>('canvas');
  private readonly browser = isPlatformBrowser(inject(PLATFORM_ID));
  private chart: ChartJs | null = null;

  constructor() {
    effect(() => {
      this.labels();
      this.series();
      this.kind();
      this.horizontal();
      this.stacked();
      this.draw();
    });
    afterNextRender(() => this.draw());
  }

  private draw(): void {
    if (!this.browser) {
      return;
    }

    const element = this.canvas()?.nativeElement;
    if (!element) {
      return;
    }

    this.chart?.destroy();
    this.chart = null;

    const labels = this.labels();
    const series = this.series();
    if (labels.length === 0 || series.length === 0) {
      return;
    }

    const kind = this.kind();
    const stacked = this.stacked();
    const configuration: ChartConfiguration = {
      type: kind,
      data: {
        labels,
        datasets: series.map((item, index) => ({
          label: item.label,
          data: item.data,
          backgroundColor:
            item.colors ??
            (kind === 'doughnut'
              ? labels.map((_, slice) => COLORS[slice % COLORS.length])
              : COLORS[index % COLORS.length]),
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: kind === 'bar' && this.horizontal() ? 'y' : 'x',
        scales:
          kind === 'doughnut'
            ? undefined
            : {
                x: { stacked, beginAtZero: true },
                y: { stacked, beginAtZero: true },
              },
      },
    };

    this.chart = new ChartJs(element, configuration);
  }
}
