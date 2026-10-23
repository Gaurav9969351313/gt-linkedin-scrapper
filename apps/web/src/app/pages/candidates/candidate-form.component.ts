import { ChangeDetectionStrategy, Component, OnChanges, computed, inject, input, output } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { Candidate, CandidateInput, TagOption } from '../../core/models';

@Component({
  selector: 'app-candidate-form',
  standalone: true,
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <form [formGroup]="form" (ngSubmit)="submit()" class="form-grid" novalidate>
      <div class="field">
        <label for="c-name">Name</label>
        <input id="c-name" class="input" formControlName="name" autocomplete="off" />
      </div>
      <div class="field">
        <label for="c-number">Number</label>
        <input id="c-number" class="input" formControlName="number" inputmode="tel" />
      </div>
      <div class="field">
        <label for="c-sub">Subscription</label>
        <input id="c-sub" class="input" formControlName="subscription" />
      </div>
      <div class="field">
        <label for="c-tag">Tag</label>
        <select id="c-tag" class="select" formControlName="tag">
          @for (t of tagOptions(); track t.name) { <option [value]="t.name">{{ t.label }}</option> }
        </select>
      </div>
      <div class="field">
        <label for="c-email">Email</label>
        <input id="c-email" class="input" type="email" formControlName="email" autocomplete="off" />
      </div>
      <div class="field">
        <label for="c-pass">Email password</label>
        <input id="c-pass" class="input" type="password" formControlName="email_password" autocomplete="new-password"
               [attr.aria-describedby]="candidate() ? 'c-pass-hint' : null" />
        @if (candidate()) { <span id="c-pass-hint" class="hint">Leave blank to keep the current password.</span> }
      </div>
      <div class="field span-all">
        <label for="c-subject">Email subject</label>
        <input id="c-subject" class="input" formControlName="email_subject" />
      </div>
      <div class="field span-all">
        <label for="c-resume">Resume <span class="muted">(.pdf or .docx)</span></label>
        <input id="c-resume" class="input" type="file" accept=".pdf,.docx" (change)="onFile($event)"
               [attr.aria-describedby]="candidate()?.resume ? 'c-resume-hint' : null" />
        @if (candidate()?.resume) { <span id="c-resume-hint" class="hint">Current: <span class="mono">{{ candidate()!.resume }}</span></span> }
      </div>
      <div class="field span-all">
        <label for="c-body">Email body (HTML)</label>
        <textarea id="c-body" class="textarea" formControlName="email_body"></textarea>
      </div>
      <label class="checkbox span-all"><input type="checkbox" formControlName="is_active" /> Active</label>

      @if (submitted && form.invalid) {
        <div class="alert alert-error span-all" role="alert">Fill in all required fields{{ form.controls.email.errors?.['email'] ? ' and use a valid email' : '' }}.</div>
      }

      <div class="actions span-all">
        @if (showCancel()) {
          <button type="button" class="btn btn-secondary" (click)="cancel.emit()">Cancel</button>
        }
        <button type="submit" class="btn btn-primary" [disabled]="saving()">{{ saving() ? 'Saving…' : submitLabel() }}</button>
      </div>
    </form>
  `,
  styles: `.actions { display: flex; justify-content: flex-end; gap: 8px; }`,
})
export class CandidateFormComponent implements OnChanges {
  private fb = inject(FormBuilder);

  candidate = input<Candidate | null>(null);
  tags = input<TagOption[]>([]);

  /** Active tags, plus the candidate's current tag if it has since been deactivated. */
  tagOptions = computed<{ name: string; label: string }[]>(() => {
    const current = this.candidate()?.tag;
    const options = this.tags().map(t => ({ name: t.name, label: t.label }));
    return current && !options.some(o => o.name === current)
      ? [...options, { name: current, label: `${current} (inactive)` }]
      : options;
  });
  saving = input(false);
  showCancel = input(true);
  submitLabel = input('Save candidate');
  save = output<CandidateInput>();
  cancel = output<void>();

  submitted = false;
  private resumeFile: File | null = null;

  form = this.fb.nonNullable.group({
    name: ['', Validators.required],
    number: ['', Validators.required],
    subscription: ['', Validators.required],
    is_active: [true],
    email: ['', [Validators.required, Validators.email]],
    email_password: [''],
    tag: ['', Validators.required],
    email_subject: ['', Validators.required],
    email_body: ['', Validators.required],
  });

  ngOnChanges(): void {
    const c = this.candidate();
    this.submitted = false;
    this.resumeFile = null;
    this.form.reset({
      name: c?.name ?? '',
      number: c?.number ?? '',
      subscription: c?.subscription ?? '',
      is_active: c?.is_active ?? true,
      email: c?.email ?? '',
      email_password: '',
      tag: c?.tag ?? this.tags()[0]?.name ?? '',
      email_subject: c?.email_subject ?? '',
      email_body: c?.email_body ?? '',
    });
    // Password is required for new candidates only.
    const pw = this.form.controls.email_password;
    pw.setValidators(c ? [] : [Validators.required]);
    pw.updateValueAndValidity();
  }

  onFile(event: Event): void {
    this.resumeFile = (event.target as HTMLInputElement).files?.[0] ?? null;
  }

  submit(): void {
    this.submitted = true;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.save.emit({ ...this.form.getRawValue(), resume_file: this.resumeFile });
  }
}
