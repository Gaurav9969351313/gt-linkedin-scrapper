import { ChangeDetectionStrategy, Component, ElementRef, OnInit, ViewChild, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/error-message';
import { Candidate, CandidateInput, TagOption } from '../../core/models';
import { IconComponent } from '../../shared/icon.component';
import { CandidateFormComponent } from './candidate-form.component';

@Component({
  selector: 'app-candidates',
  standalone: true,
  imports: [FormsModule, IconComponent, CandidateFormComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './candidates.component.html',
  styleUrl: './candidates.component.scss',
})
export class CandidatesComponent implements OnInit {
  private api = inject(ApiService);

  @ViewChild('formDialog') formDialog!: ElementRef<HTMLDialogElement>;
  @ViewChild('deleteDialog') deleteDialog!: ElementRef<HTMLDialogElement>;

  candidates = signal<Candidate[]>([]);
  tags = signal<TagOption[]>([]);
  tagFilter = '';
  loading = signal(true);
  error = signal<string | null>(null);

  editing = signal<Candidate | null>(null);
  saving = signal(false);
  formError = signal<string | null>(null);

  deleting = signal<Candidate | null>(null);
  deleteBusy = signal(false);

  ngOnInit(): void {
    this.api.getTags().subscribe({ next: tags => this.tags.set(tags) });
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.getCandidates(this.tagFilter || undefined).subscribe({
      next: list => {
        this.candidates.set(list);
        this.loading.set(false);
      },
      error: err => {
        this.error.set(errorMessage(err, 'Could not load candidates.'));
        this.loading.set(false);
      },
    });
  }

  openForm(candidate: Candidate | null): void {
    this.editing.set(candidate);
    this.formError.set(null);
    this.formDialog.nativeElement.showModal();
  }

  closeForm(): void {
    this.formDialog.nativeElement.close();
  }

  save(input: CandidateInput): void {
    const current = this.editing();
    this.saving.set(true);
    this.formError.set(null);
    const req = current ? this.api.updateCandidate(current.id, input) : this.api.createCandidate(input);
    req.subscribe({
      next: () => {
        this.saving.set(false);
        this.closeForm();
        this.load();
      },
      error: err => {
        this.saving.set(false);
        this.formError.set(errorMessage(err, 'Could not save the candidate.'));
      },
    });
  }

  confirmDelete(candidate: Candidate): void {
    this.deleting.set(candidate);
    this.deleteDialog.nativeElement.showModal();
  }

  doDelete(): void {
    const target = this.deleting();
    if (!target) return;
    this.deleteBusy.set(true);
    this.api.deleteCandidate(target.id).subscribe({
      next: () => {
        this.deleteBusy.set(false);
        this.deleteDialog.nativeElement.close();
        this.candidates.update(list => list.filter(c => c.id !== target.id));
      },
      error: err => {
        this.deleteBusy.set(false);
        this.deleteDialog.nativeElement.close();
        this.error.set(errorMessage(err, 'Could not delete the candidate.'));
      },
    });
  }

  fileName(path: string | null): string {
    return path ? path.split(/[\\/]/).pop() ?? path : '';
  }
}
