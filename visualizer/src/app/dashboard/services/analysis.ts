import { HttpClient } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Analysis } from '../interfaces/analysis';

@Service()
export class AnalysisService {
  private readonly http = inject(HttpClient);

  load(): Observable<Analysis> {
    return this.http.get<Analysis>('/analysis.json');
  }
}
