import { isPlatformBrowser } from '@angular/common';
import { Component, PLATFORM_ID, afterNextRender, inject, signal } from '@angular/core';

import { Analysis } from '../../interfaces/analysis';
import { AnalysisService } from '../../services/analysis';
import { Distribution } from '../distribution/distribution';
import { Overview } from '../overview/overview';
import { QuestionPanel } from '../question-panel/question-panel';
import { Rules } from '../rules/rules';

@Component({
  imports: [Overview, QuestionPanel, Distribution, Rules],
  selector: 'app-dashboard',
  styleUrl: './dashboard.css',
  templateUrl: './dashboard.html',
})
export class Dashboard {
  private readonly analysisService = inject(AnalysisService);
  private readonly browser = isPlatformBrowser(inject(PLATFORM_ID));

  readonly analysis = signal<Analysis | null>(null);
  readonly openId = signal<string | null>(null);

  constructor() {
    afterNextRender(() => {
      if (!this.browser) {
        return;
      }
      this.analysisService.load().subscribe((analysis) => {
        this.analysis.set(analysis);
        this.openId.set(analysis.questions[0]?.id ?? null);
      });
    });
  }

  toggle(id: string): void {
    this.openId.update((current) => (current === id ? null : id));
  }
}
