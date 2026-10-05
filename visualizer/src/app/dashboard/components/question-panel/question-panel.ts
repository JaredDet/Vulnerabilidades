import { Component, input, output } from '@angular/core';

import { AnalysisQuestion } from '../../interfaces/analysis';

@Component({
  selector: 'app-question-panel',
  styleUrl: './question-panel.css',
  templateUrl: './question-panel.html',
})
export class QuestionPanel {
  readonly statuses = input<Record<string, string>>({});
  readonly question = input.required<AnalysisQuestion>();
  readonly open = input(false);
  readonly toggled = output<void>();

  segments(markdown: string): Array<{ bold: boolean; text: string }> {
    return markdown.split('**').map((text, index) => ({ bold: index % 2 === 1, text }));
  }
}
