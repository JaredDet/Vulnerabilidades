import {
  afterEveryRender,
  Component,
  computed,
  effect,
  ElementRef,
  input,
  signal,
  viewChild,
} from '@angular/core';

import { AnalysisValue } from '../../interfaces/analysis';
import { formatAnalysisNumber } from '../chart/chart';

export interface DataTableColumn {
  key: string;
  filter?: boolean;
}

export interface DataTableSort {
  key: string;
  direction: 'asc' | 'desc';
}

@Component({
  selector: 'app-data-table',
  styleUrl: './data-table.css',
  templateUrl: './data-table.html',
})
export class DataTable {
  readonly columns = input.required<DataTableColumn[]>();
  readonly rows = input.required<Array<Record<string, AnalysisValue>>>();
  readonly nullText = input('');
  readonly title = input('');
  readonly initialSort = input<DataTableSort | null>(null);

  readonly pageSizes = [5, 10, 20];
  private readonly pageSizeSelect = viewChild<ElementRef<HTMLSelectElement>>('pageSizeSelect');
  readonly search = signal('');
  readonly filters = signal<Record<string, string>>({});
  readonly sort = signal<DataTableSort | null>(null);
  readonly pageSize = signal(10);
  readonly page = signal(0);

  readonly filterColumns = computed(() => this.columns().filter((column) => column.filter));

  readonly filterOptions = computed(() => {
    const options: Record<string, string[]> = {};
    for (const column of this.filterColumns()) {
      const values = new Set(this.rows().map((row) => this.cell(row, column.key)));
      options[column.key] = [...values].sort((left, right) => left.localeCompare(right));
    }
    return options;
  });

  readonly filtered = computed(() => {
    const query = this.search().trim().toLowerCase();
    const selected = this.filters();
    const columns = this.columns();
    const matching = this.rows().filter((row) => {
      for (const column of columns) {
        const choice = selected[column.key];
        if (column.filter && choice && this.cell(row, column.key) !== choice) {
          return false;
        }
      }
      if (query === '') {
        return true;
      }
      return columns.some((column) => this.cell(row, column.key).toLowerCase().includes(query));
    });
    const sort = this.sort() ?? this.initialSort();
    if (!sort) {
      return matching;
    }
    return [...matching].sort((left, right) => this.compare(left, right, sort));
  });

  readonly pageCount = computed(() => {
    const total = this.filtered().length;
    if (total === 0) {
      return 1;
    }
    return Math.ceil(total / this.pageSize());
  });

  readonly safePage = computed(() => Math.min(this.page(), this.pageCount() - 1));

  readonly pageRows = computed(() => {
    const start = this.safePage() * this.pageSize();
    return this.filtered().slice(start, start + this.pageSize());
  });

  readonly rangeLabel = computed(() => {
    const total = this.filtered().length;
    if (total === 0) {
      return '0–0 / 0';
    }
    const start = this.safePage() * this.pageSize() + 1;
    const end = Math.min(total, (this.safePage() + 1) * this.pageSize());
    return `${start}–${end} / ${total}`;
  });

  readonly activeSort = computed(() => this.sort() ?? this.initialSort());

  constructor() {
    effect(() => {
      this.rows();
      this.page.set(0);
    });
    afterEveryRender(() => {
      const select = this.pageSizeSelect()?.nativeElement;
      if (select) {
        select.value = String(this.pageSize());
      }
    });
  }

  cell(row: Record<string, AnalysisValue>, key: string): string {
    return displayValue(row[key], key, this.nullText());
  }

  onSearch(event: Event): void {
    this.search.set((event.target as HTMLInputElement).value);
    this.page.set(0);
  }

  onFilter(key: string, event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.filters.update((current) => ({ ...current, [key]: value }));
    this.page.set(0);
  }

  onPageSize(event: Event): void {
    this.pageSize.set(Number((event.target as HTMLSelectElement).value));
    this.page.set(0);
  }

  toggleSort(key: string): void {
    const current = this.activeSort();
    const direction = current?.key === key && current.direction === 'asc' ? 'desc' : 'asc';
    this.sort.set({ key, direction });
    this.page.set(0);
  }

  previous(): void {
    this.page.set(Math.max(0, this.safePage() - 1));
  }

  next(): void {
    this.page.set(Math.min(this.pageCount() - 1, this.safePage() + 1));
  }

  private compare(
    left: Record<string, AnalysisValue>,
    right: Record<string, AnalysisValue>,
    sort: DataTableSort,
  ): number {
    const leftValue = left[sort.key];
    const rightValue = right[sort.key];
    const leftMissing = leftValue === null || leftValue === undefined;
    const rightMissing = rightValue === null || rightValue === undefined;
    let result = 0;
    if (leftMissing || rightMissing) {
      return Number(leftMissing) - Number(rightMissing);
    }
    if (typeof leftValue === 'number' && typeof rightValue === 'number') {
      result = leftValue - rightValue;
    } else {
      result = this.cell(left, sort.key).localeCompare(this.cell(right, sort.key));
    }
    return sort.direction === 'asc' ? result : -result;
  }
}

function displayValue(value: AnalysisValue | undefined, key: string, nullText: string): string {
  if (value === null || value === undefined) {
    return nullText;
  }
  if (typeof value === 'number') {
    return formatAnalysisNumber(value, key);
  }
  if (typeof value === 'string' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => displayValue(item, key, nullText)).join(', ');
  }
  return '';
}
