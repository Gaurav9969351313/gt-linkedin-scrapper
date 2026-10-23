import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';

import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/error-message';
import { Candidate, CandidateInput, TagOption } from '../../core/models';
import { IconComponent } from '../../shared/icon.component';
import { CandidateFormComponent } from '../candidates/candidate-form.component';

/** My Candidature: a regular user's single candidate, created once and then edited. */
@Component({
  selector: 'app-my-candidature',
  standalone: true,
  imports: [IconComponent, CandidateFormComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="page">
      <header class="page-header">
        <div>
          <h1>My Candidature</h1>
          <p class="muted">
            @if (candidate()) { Your candidature, used for outgoing applications. }
            @else { Create your candidature. Each account can have one. }
          </p>
        </div>
        @if (candidate(); as c) {
          <div class="status">
            <span class="badge badge-tag">{{ c.tag }}</span>
            @if (c.is_active) { <span class="badge badge-success">Active</span> } @else { <span class="badge">Inactive</span> }
          </div>
        }
      </header>

      @if (error()) {
        <div class="alert alert-error" role="alert"><app-icon name="alert" [size]="18" /> {{ error() }}</div>
      }
      @if (notice()) {
        <div class="alert alert-success" role="status">{{ notice() }}</div>
      }

      <section class="card" aria-label="My Candidature">
        @if (loading()) {
          <p class="muted" role="status">Loading…</p>
        } @else {
          <app-candidate-form
            [candidate]="candidate()"
            [tags]="tags()"
            [saving]="saving()"
            [showCancel]="false"
            [submitLabel]="candidate() ? 'Save changes' : 'Create my Candidature'"
            (save)="save($event)"
          />
        }
      </section>
    </div>
  `,
  styles: `.status { display: flex; gap: 8px; }`,
})
export class MyCandidatureComponent implements OnInit {
  private api = inject(ApiService);

  candidate = signal<Candidate | null>(null);
  tags = signal<TagOption[]>([]);
  loading = signal(true);
  saving = signal(false);
  error = signal<string | null>(null);
  notice = signal<string | null>(null);

  ngOnInit(): void {
    this.api.getTags().subscribe({ next: tags => this.tags.set(tags) });
    this.api.getMyCandidate().subscribe({
      next: c => {
        this.candidate.set(c);
        this.loading.set(false);
      },
      error: err => {
        this.error.set(errorMessage(err, 'Could not load your candidature.'));
        this.loading.set(false);
      },
    });
  }

  save(input: CandidateInput): void {
    const current = this.candidate();
    this.saving.set(true);
    this.error.set(null);
    this.notice.set(null);
    const req = current ? this.api.updateCandidate(current.id, input) : this.api.createCandidate(input);
    req.subscribe({
      next: saved => {
        this.candidate.set(saved);
        this.notice.set(current ? 'Changes saved.' : 'Your candidature was created.');
        this.saving.set(false);
      },
      error: err => {
        this.error.set(errorMessage(err, 'Could not save your candidature.'));
        this.saving.set(false);
      },
    });
  }
}
