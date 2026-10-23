import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, ElementRef, OnInit, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/error-message';
import { RunLogEntry, ScrapeJob, ScrapeJobInput, TagOption } from '../../core/models';
import { IconComponent } from '../../shared/icon.component';
import { CRON_PRESETS, CRON_TIMEZONE, describeCron } from './cron';

/** LinkedIn scrape job management (super admin). Changes are pushed to Prefect by the API. */
@Component({
  selector: 'app-jobs',
  standalone: true,
  imports: [FormsModule, DatePipe, DecimalPipe, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './jobs.component.html',
  styleUrl: './jobs.component.scss',
})
export class JobsComponent implements OnInit {
  private api = inject(ApiService);

  @ViewChild('formDialog') formDialog!: ElementRef<HTMLDialogElement>;
  @ViewChild('deleteDialog') deleteDialog!: ElementRef<HTMLDialogElement>;
  @ViewChild('runsDialog') runsDialog!: ElementRef<HTMLDialogElement>;

  readonly presets = CRON_PRESETS;
  readonly timezone = CRON_TIMEZONE;
  readonly describeCron = describeCron;

  jobs = signal<ScrapeJob[]>([]);
  tags = signal<TagOption[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);
  notice = signal<string | null>(null);
  warning = signal<string | null>(null);
  busyId = signal<string | null>(null);

  editing = signal<ScrapeJob | null>(null);
  form: ScrapeJobInput = { keyword: '', scroll_count: 5, tag: '', cron_expression: '30 7 * * *' };
  saving = signal(false);
  formError = signal<string | null>(null);

  deleting = signal<ScrapeJob | null>(null);
  deleteBusy = signal(false);

  runsFor = signal<ScrapeJob | null>(null);
  runs = signal<RunLogEntry[]>([]);
  runsLoading = signal(false);

  tagLabels = computed(() => new Map(this.tags().map(t => [t.name, t.label])));

  /** Active tags, plus the edited job's current tag if it has since been deactivated. */
  tagOptions = computed(() => {
    const options = this.tags().map(t => ({ name: t.name, label: t.label }));
    const current = this.editing()?.tag;
    return current && !options.some(o => o.name === current)
      ? [...options, { name: current, label: `${current} (inactive)` }]
      : options;
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({ jobs: this.api.getJobs(), tags: this.api.getTags() }).subscribe({
      next: ({ jobs, tags }) => {
        this.jobs.set(jobs);
        this.tags.set(tags);
        this.loading.set(false);
      },
      error: err => {
        this.error.set(errorMessage(err, 'Could not load jobs.'));
        this.loading.set(false);
      },
    });
  }

  tagLabel(name: string): string {
    return this.tagLabels().get(name) ?? name;
  }

  // ---------- create / edit ----------

  openForm(job: ScrapeJob | null): void {
    this.editing.set(job);
    this.form = job
      ? { keyword: job.keyword, scroll_count: job.scroll_count, tag: job.tag, cron_expression: job.cron_expression }
      : { keyword: '', scroll_count: 5, tag: this.tags()[0]?.name ?? '', cron_expression: '30 7 * * *' };
    this.formError.set(null);
    this.formDialog.nativeElement.showModal();
  }

  applyPreset(cron: string): void {
    if (cron) this.form.cron_expression = cron;
  }

  save(): void {
    const current = this.editing();
    this.saving.set(true);
    this.formError.set(null);
    const body = { ...this.form, scroll_count: Number(this.form.scroll_count) };
    const req = current ? this.api.updateJob(current.id, body) : this.api.createJob(body);
    req.subscribe({
      next: saved => {
        this.saving.set(false);
        this.formDialog.nativeElement.close();
        this.upsert(saved);
        this.report(saved.warning ?? null, current ? `Job #${saved.id} updated.` : `Job #${saved.id} created and scheduled.`);
      },
      error: err => {
        this.saving.set(false);
        this.formError.set(errorMessage(err, 'Could not save the job.'));
      },
    });
  }

  // ---------- actions ----------

  toggleHold(job: ScrapeJob): void {
    this.busyId.set(`hold-${job.id}`);
    const req = job.on_hold ? this.api.resumeJob(job.id) : this.api.holdJob(job.id);
    req.subscribe({
      next: saved => {
        this.busyId.set(null);
        this.upsert(saved);
        this.report(saved.warning ?? null, saved.on_hold ? `Job #${job.id} is on hold. Its schedule is paused.` : `Job #${job.id} resumed.`);
      },
      error: err => {
        this.busyId.set(null);
        this.error.set(errorMessage(err));
      },
    });
  }

  runNow(job: ScrapeJob): void {
    this.busyId.set(`run-${job.id}`);
    this.api.runJob(job.id).subscribe({
      next: () => {
        this.busyId.set(null);
        this.report(null, `Job #${job.id} started. The worker picks it up within a few seconds; refresh to see its status.`);
      },
      error: err => {
        this.busyId.set(null);
        this.error.set(errorMessage(err, 'Could not start the job.'));
      },
    });
  }

  showRuns(job: ScrapeJob): void {
    this.runsFor.set(job);
    this.runs.set([]);
    this.runsLoading.set(true);
    this.runsDialog.nativeElement.showModal();
    this.api.getJobRuns(job.id).subscribe({
      next: runs => {
        this.runs.set(runs);
        this.runsLoading.set(false);
      },
      error: () => this.runsLoading.set(false),
    });
  }

  confirmDelete(job: ScrapeJob): void {
    this.deleting.set(job);
    this.deleteDialog.nativeElement.showModal();
  }

  doDelete(): void {
    const job = this.deleting();
    if (!job) return;
    this.deleteBusy.set(true);
    this.api.deleteJob(job.id).subscribe({
      next: res => {
        this.deleteBusy.set(false);
        this.deleteDialog.nativeElement.close();
        this.jobs.update(list => list.filter(j => j.id !== job.id));
        this.report(res.warning, `Job #${job.id} deleted.`);
      },
      error: err => {
        this.deleteBusy.set(false);
        this.deleteDialog.nativeElement.close();
        this.error.set(errorMessage(err, 'Could not delete the job.'));
      },
    });
  }

  private upsert(job: ScrapeJob): void {
    this.jobs.update(list => (list.some(j => j.id === job.id) ? list.map(j => (j.id === job.id ? job : j)) : [...list, job]));
  }

  private report(warning: string | null, message: string): void {
    this.error.set(null);
    this.warning.set(warning);
    this.notice.set(warning ? null : message);
  }
}
