import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth.service';
import { errorMessage } from '../../core/error-message';
import { ROLE_LABELS, Role } from '../../core/models';
import { IconComponent } from '../../shared/icon.component';

@Component({
  selector: 'app-accept-invite',
  standalone: true,
  imports: [FormsModule, RouterLink, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="auth-page">
      <section class="card auth-card" aria-labelledby="inv-title">
        <div class="auth-brand"><span class="mark"><app-icon name="shield" [size]="20" /></span> LinkedIn Scraper Console</div>

        @if (checking()) {
          <p class="muted" role="status">Checking your invitation…</p>
        } @else if (invite()) {
          <div>
            <h1 id="inv-title">Accept invitation</h1>
            <p class="muted">You've been invited as <strong>{{ roleLabel(invite()!.role) }}</strong>. Set a password to finish.</p>
          </div>

          @if (error()) {
            <div class="alert alert-error" role="alert"><app-icon name="alert" [size]="18" /> {{ error() }}</div>
          }

          <form (ngSubmit)="submit()" #f="ngForm">
            <div class="field">
              <label for="email">Email</label>
              <input id="email" class="input" type="email" name="email" [value]="invite()!.email" readonly autocomplete="username" />
            </div>
            <div class="field">
              <label for="name">Full name</label>
              <input id="name" class="input" name="name" autocomplete="name" required [(ngModel)]="name" />
            </div>
            <div class="field">
              <label for="password">Password</label>
              <input id="password" class="input" type="password" name="password" autocomplete="new-password" required minlength="10" [(ngModel)]="password" aria-describedby="pw-hint" />
              <span id="pw-hint" class="hint">At least 10 characters.</span>
            </div>
            <button class="btn btn-primary" type="submit" [disabled]="loading() || !f.valid">
              {{ loading() ? 'Creating account…' : 'Create account' }}
            </button>
          </form>
        } @else {
          <div>
            <h1 id="inv-title">Invitation unavailable</h1>
            <p class="muted">{{ error() }}</p>
          </div>
          <a class="btn btn-secondary" routerLink="/login">Go to sign in</a>
        }
      </section>
    </div>
  `,
})
export class AcceptInviteComponent implements OnInit {
  private auth = inject(AuthService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  token = '';
  name = '';
  password = '';
  checking = signal(true);
  loading = signal(false);
  invite = signal<{ email: string; role: string } | null>(null);
  error = signal<string | null>(null);

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get('token') ?? '';
    if (!this.token) {
      this.error.set('This invitation link is missing its token.');
      this.checking.set(false);
      return;
    }
    this.auth.lookupInvitation(this.token).subscribe({
      next: inv => {
        this.invite.set(inv);
        this.checking.set(false);
      },
      error: err => {
        this.error.set(errorMessage(err, 'This invitation link is invalid.'));
        this.checking.set(false);
      },
    });
  }

  roleLabel(role: string): string {
    return ROLE_LABELS[role as Role] ?? role;
  }

  submit(): void {
    this.loading.set(true);
    this.error.set(null);
    this.auth.acceptInvitation(this.token, this.name, this.password).subscribe({
      next: () => this.router.navigate(['/dashboard']),
      error: err => {
        this.error.set(errorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
