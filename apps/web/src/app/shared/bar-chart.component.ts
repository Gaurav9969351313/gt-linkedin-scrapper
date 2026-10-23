import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { CountRow } from '../core/models';

/** Accessible bar chart: horizontal bars for categories, vertical columns for time series. */
@Component({
  selector: 'app-bar-chart',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (orientation() === 'horizontal') {
      <ul class="hbars" [attr.aria-label]="label()">
        @for (row of rows(); track row.label) {
          <li>
            <span class="lbl mono">{{ row.label }}</span>
            <span class="track"><span class="bar" [style.width.%]="pct(row.count)"></span></span>
            <span class="val">{{ row.count }}</span>
          </li>
        }
      </ul>
    } @else {
      <div class="cols" role="list" [attr.aria-label]="label()">
        @for (row of rows(); track row.label) {
          <div class="col" role="listitem" [attr.aria-label]="row.label + ': ' + row.count" [title]="row.label + ': ' + row.count">
            <span class="bar" [style.height.%]="pct(row.count)"></span>
          </div>
        }
      </div>
      @if (rows().length) {
        <div class="axis mono muted">
          <span>{{ rows()[0].label }}</span>
          <span>{{ rows()[rows().length - 1].label }}</span>
        </div>
      }
    }
  `,
  styles: `
    .hbars { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
    .hbars li { display: grid; grid-template-columns: minmax(80px, 120px) 1fr 48px; align-items: center; gap: 12px; font-size: .85rem; }
    .lbl { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .track { height: 10px; background: var(--surface-2); border-radius: 999px; overflow: hidden; }
    .hbars .bar { display: block; height: 100%; background: var(--chart); border-radius: 999px; min-width: 2px; }
    .val { text-align: right; font-variant-numeric: tabular-nums; }
    .cols { display: flex; align-items: flex-end; gap: 3px; height: 180px; border-bottom: 1px solid var(--border); }
    .col { flex: 1; height: 100%; display: flex; align-items: flex-end; min-width: 2px; }
    .col .bar { width: 100%; background: var(--chart); border-radius: 3px 3px 0 0; min-height: 2px; }
    .col:hover .bar { background: var(--highlight); }
    .axis { display: flex; justify-content: space-between; font-size: .75rem; margin-top: 8px; }
  `,
})
export class BarChartComponent {
  rows = input.required<CountRow[]>();
  label = input('Chart');
  orientation = input<'horizontal' | 'vertical'>('horizontal');

  private max = computed(() => Math.max(1, ...this.rows().map(r => r.count)));

  pct(count: number): number {
    return (count / this.max()) * 100;
  }
}
