import { isPlatformBrowser } from '@angular/common';
import { Component, PLATFORM_ID, afterNextRender, inject, signal } from '@angular/core';

import { Analysis } from '../../interfaces/analysis';
import { AnalysisService } from '../../services/analysis';
import { Overview } from '../overview/overview';

@Component({
  imports: [Overview],
  selector: 'app-dashboard',
  styleUrl: './dashboard.css',
  templateUrl: './dashboard.html',
})
export class Dashboard {
  private readonly analysisService = inject(AnalysisService);
  private readonly browser = isPlatformBrowser(inject(PLATFORM_ID));

  readonly analysis = signal<Analysis | null>(null);

  constructor() {
    afterNextRender(() => {
      if (!this.browser) {
        return;
      }
      this.analysisService.load().subscribe((analysis) => this.analysis.set(analysis));
    });
  }
}
