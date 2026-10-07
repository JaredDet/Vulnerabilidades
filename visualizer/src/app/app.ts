import { Component } from '@angular/core';

import { Dashboard } from './dashboard/components/dashboard/dashboard';

@Component({
  imports: [Dashboard],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App {}
