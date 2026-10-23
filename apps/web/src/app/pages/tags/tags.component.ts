import { ChangeDetectionStrategy, Component, ElementRef, OnInit, ViewChild, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../../core/api.service';
import { errorMessage } from '../../core/error-message';
import { TagOption } from '../../core/models';
import { IconComponent } from '../../shared/icon.component';

/** Tag management (super admin): tags group scrape jobs, their email records and candidates. */
@Component({
  selector: 'app-tags',
  standalone: true,
  imports: [FormsModule, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './tags.component.html',
  styleUrl: './tags.component.scss',
})
export class TagsComponent implements OnInit {
  private api = inject(ApiService);

  @ViewChild('editDialog') editDialog!: ElementRef<HTMLDialogElement>;
  @ViewChild('deleteDialog') deleteDialog!: ElementRef<HTMLDialogElement>;

  tags = signal<TagOption[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);
  notice = signal<string | null>(null);

  editing = signal<TagOption | null>(null);
  form = { name: '', label: '', description: '', is_active: true };
  saving = signal(false);
  formError = signal<string | null>(null);

  deleting = signal<TagOption | null>(null);
  deleteBusy = signal(false);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.getAllTags().subscribe({
      next: tags => {
        this.tags.set(tags);
        this.loading.set(false);
      },
      error: err => {
        this.error.set(errorMessage(err, 'Could not load tags.'));
        this.loading.set(false);
      },
    });
  }

  inUse(tag: TagOption): boolean {
    return !!tag.usage && (tag.usage.jobs > 0 || tag.usage.candidates > 0);
  }

  openForm(tag: TagOption | null): void {
    this.editing.set(tag);
    this.form = {
      name: tag?.name ?? '',
      label: tag?.label ?? '',
      description: tag?.description ?? '',
      is_active: tag?.is_active ?? true,
    };
    this.formError.set(null);
    this.editDialog.nativeElement.showModal();
  }

  /** Suggest a name from the label while creating, until the name is edited by hand. */
  onLabelChange(label: string): void {
    if (!this.editing()) {
      this.form.name = label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 64);
    }
  }

  save(): void {
    const current = this.editing();
    const description = this.form.description.trim() || null;
    this.saving.set(true);
    this.formError.set(null);
    const req = current
      ? this.api.updateTag(current.id, { label: this.form.label, description, is_active: this.form.is_active })
      : this.api.createTag({ name: this.form.name, label: this.form.label, description });
    req.subscribe({
      next: saved => {
        this.saving.set(false);
        this.editDialog.nativeElement.close();
        this.tags.update(list => (current ? list.map(t => (t.id === saved.id ? saved : t)) : [...list, saved]));
        this.notice.set(current ? `Tag “${saved.label}” updated.` : `Tag “${saved.label}” created.`);
      },
      error: err => {
        this.saving.set(false);
        this.formError.set(errorMessage(err, 'Could not save the tag.'));
      },
    });
  }

  toggleActive(tag: TagOption): void {
    this.api.updateTag(tag.id, { label: tag.label, description: tag.description, is_active: !tag.is_active }).subscribe({
      next: saved => {
        this.tags.update(list => list.map(t => (t.id === saved.id ? saved : t)));
        this.notice.set(saved.is_active ? `“${saved.label}” is active again.` : `“${saved.label}” deactivated. Existing jobs and candidates keep it.`);
      },
      error: err => this.error.set(errorMessage(err)),
    });
  }

  confirmDelete(tag: TagOption): void {
    this.deleting.set(tag);
    this.deleteDialog.nativeElement.showModal();
  }

  doDelete(): void {
    const tag = this.deleting();
    if (!tag) return;
    this.deleteBusy.set(true);
    this.api.deleteTag(tag.id).subscribe({
      next: () => {
        this.deleteBusy.set(false);
        this.deleteDialog.nativeElement.close();
        this.tags.update(list => list.filter(t => t.id !== tag.id));
        this.notice.set(`Tag “${tag.label}” deleted.`);
      },
      error: err => {
        this.deleteBusy.set(false);
        this.deleteDialog.nativeElement.close();
        this.error.set(errorMessage(err, 'Could not delete the tag.'));
      },
    });
  }
}
