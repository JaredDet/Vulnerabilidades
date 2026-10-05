import { Component, computed, input } from '@angular/core';

import { Analysis } from '../../interfaces/analysis';

@Component({
  selector: 'app-overview',
  styleUrl: './overview.css',
  templateUrl: './overview.html',
})
export class Overview {
  readonly analysis = input.required<Analysis>();

  readonly summaryItems = computed(() => {
    const summary = this.analysis().summary;
    return [
      { value: summary.repositories, label: 'repositories' },
      { value: summary.finding_records, label: 'finding_records' },
      { value: summary.component_records, label: 'component_records' },
      { value: summary.questions, label: 'questions' },
    ];
  });
}
