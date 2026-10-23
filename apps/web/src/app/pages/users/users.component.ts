import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, ElementRef, OnInit, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Observable, forkJoin } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { errorMessage } from '../../core/error-message';
import { AppUser, Invitation, InvitationResult, ROLE_LABELS, Role } from '../../core/models';
import { IconComponent } from '../../shared/icon.component';

type Tab = 'requests' | 'members' | 'invitations';

@Component({
  selector: 'app-users',
  standalone: true,
  imports: [FormsModule, DatePipe, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './users.component.html',
  styleUrl: './users.component.scss',
})
export class UsersComponent implements OnInit {
  private api = inject(ApiService);
  auth = inject(AuthService);

  @ViewChild('inviteDialog') inviteDialog!: ElementRef<HTMLDialogElement>;

  readonly roleLabels = ROLE_LABELS;
  tab = signal<Tab>('requests');
  users = signal<AppUser[]>([]);
  invitations = signal<Invitation[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);
  notice = signal<string | null>(null);
  busyId = signal<string | null>(null);

  /** Role chosen per pending request before approving. */
  approveRole: Record<number, Role> = {};

  inviteEmail = '';
  inviteRole: Role = 'user';
  inviting = signal(false);
  inviteError = signal<string | null>(null);
  inviteResult = signal<InvitationResult | null>(null);
  copied = signal(false);

  assignable = computed<Role[]>(() => (this.auth.isSuperAdmin() ? ['user', 'admin', 'super_admin'] : ['user']));
  requests = computed(() => this.users().filter(u => u.status === 'pending'));
  members = computed(() => this.users().filter(u => u.status !== 'pending'));

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({ users: this.api.getUsers(), invitations: this.api.getInvitations() }).subscribe({
      next: ({ users, invitations }) => {
        this.users.set(users);
        this.invitations.set(invitations);
        if (this.tab() === 'requests' && !users.some(u => u.status === 'pending')) this.tab.set('members');
        this.loading.set(false);
      },
      error: err => {
        this.error.set(errorMessage(err, 'Could not load users.'));
        this.loading.set(false);
      },
    });
  }

  // ---------- user actions ----------

  approve(user: AppUser): void {
    const role = this.approveRole[user.id] ?? 'user';
    this.run(`approve-${user.id}`, this.api.approveUser(user.id, role), `${user.name} can now sign in as ${ROLE_LABELS[role]}.`);
  }

  reject(user: AppUser): void {
    this.run(`reject-${user.id}`, this.api.rejectUser(user.id), `Request from ${user.name} rejected.`);
  }

  setEnabled(user: AppUser, enabled: boolean): void {
    const req = enabled ? this.api.enableUser(user.id) : this.api.disableUser(user.id);
    this.run(`toggle-${user.id}`, req, enabled ? `${user.name} re-enabled.` : `${user.name} disabled. Their session ends immediately.`);
  }

  changeRole(user: AppUser, role: Role): void {
    if (role === user.role) return;
    this.run(`role-${user.id}`, this.api.changeRole(user.id, role), `${user.name} is now ${ROLE_LABELS[role]}.`);
  }

  private run(key: string, req: Observable<AppUser>, message: string): void {
    this.busyId.set(key);
    this.error.set(null);
    this.notice.set(null);
    req.subscribe({
      next: updated => {
        this.users.update(list => list.map(u => (u.id === updated.id ? updated : u)));
        this.notice.set(message);
        this.busyId.set(null);
      },
      error: err => {
        this.error.set(errorMessage(err));
        this.busyId.set(null);
        this.load();
      },
    });
  }

  // ---------- invitations ----------

  openInvite(): void {
    this.inviteEmail = '';
    this.inviteRole = 'user';
    this.inviteError.set(null);
    this.inviteResult.set(null);
    this.copied.set(false);
    this.inviteDialog.nativeElement.showModal();
  }

  sendInvite(): void {
    this.inviting.set(true);
    this.inviteError.set(null);
    this.api.invite(this.inviteEmail, this.inviteRole).subscribe({
      next: res => this.onInvited(res),
      error: err => {
        this.inviteError.set(errorMessage(err));
        this.inviting.set(false);
      },
    });
  }

  resend(inv: Invitation): void {
    this.inviteError.set(null);
    this.copied.set(false);
    this.busyId.set(`resend-${inv.id}`);
    this.api.resendInvitation(inv.id).subscribe({
      next: res => {
        this.busyId.set(null);
        this.onInvited(res);
        this.inviteDialog.nativeElement.showModal();
      },
      error: err => {
        this.busyId.set(null);
        this.error.set(errorMessage(err));
      },
    });
  }

  revoke(inv: Invitation): void {
    this.busyId.set(`revoke-${inv.id}`);
    this.api.revokeInvitation(inv.id).subscribe({
      next: () => {
        this.busyId.set(null);
        this.invitations.update(list => list.filter(i => i.id !== inv.id));
        this.notice.set(`Invitation for ${inv.email} revoked.`);
      },
      error: err => {
        this.busyId.set(null);
        this.error.set(errorMessage(err));
      },
    });
  }

  private onInvited(res: InvitationResult): void {
    this.inviting.set(false);
    this.inviteResult.set(res);
    this.invitations.update(list => [res.invitation, ...list.filter(i => i.email !== res.invitation.email)]);
  }

  async copyLink(): Promise<void> {
    const url = this.inviteResult()?.invite_url;
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      this.copied.set(true);
    } catch {
      this.copied.set(false);
    }
  }
}
