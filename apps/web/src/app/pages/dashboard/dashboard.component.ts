import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';

import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/error-message';
import { CountRow, DashboardStats } from '../../core/models';
import { BarChartComponent } from '../../shared/bar-chart.component';
import { IconComponent } from '../../shared/icon.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [DecimalPipe, BarChartComponent, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './dashboard.component.html',
  styles: `
    .kpis { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
    .kpi { display: grid; gap: 4px; }
    .kpi-label { display: flex; align-items: center; gap: 8px; font-size: .8rem; font-weight: 500; color: var(--fg-muted); text-transform: uppercase; letter-spacing: .04em; }
    .kpi-value { font-size: 2rem; font-weight: 600; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
    .skeleton { height: 2.5rem; width: 6rem; border-radius: var(--radius-sm); background: var(--surface-2); }
  `,
})
export class DashboardComponent implements OnInit {
  private api = inject(ApiService);

  stats = signal<DashboardStats | null>(null);
  loading = signal(true);
  error = signal<string | null>(null);

  tagRows = computed<CountRow[]>(() => (this.stats()?.by_tag ?? []).map(r => ({ label: r.tag, count: r.count })));
  dateRows = computed<CountRow[]>(() => (this.stats()?.by_date ?? []).map(r => ({ label: r.date, count: r.count })));

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.getStats().subscribe({
      next: stats => {
        this.stats.set(stats);
        this.loading.set(false);
      },
      error: err => {
        this.error.set(errorMessage(err, 'Could not load dashboard data.'));
        this.loading.set(false);
      },
    });
  }
}
