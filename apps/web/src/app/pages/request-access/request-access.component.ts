import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth.service';
import { errorMessage } from '../../core/error-message';
import { IconComponent } from '../../shared/icon.component';

@Component({
  selector: 'app-request-access',
  standalone: true,
  imports: [FormsModule, RouterLink, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="auth-page">
      <section class="card auth-card" aria-labelledby="req-title">
        <div class="auth-brand"><span class="mark"><app-icon name="shield" [size]="20" /></span> LinkedIn Scraper Console</div>

        @if (done()) {
          <div>
            <h1 id="req-title">Request sent</h1>
            <p class="muted">An admin will review your request. You can sign in with the password you chose once it's approved.</p>
          </div>
          <div class="alert alert-success" role="status"><app-icon name="mail" [size]="18" /> {{ done() }}</div>
          <a class="btn btn-secondary" routerLink="/login">Back to sign in</a>
        } @else {
          <div>
            <h1 id="req-title">Request access</h1>
            <p class="muted">You won't be able to sign in until an admin approves this request.</p>
          </div>

          @if (error()) {
            <div class="alert alert-error" role="alert"><app-icon name="alert" [size]="18" /> {{ error() }}</div>
          }

          <form (ngSubmit)="submit()" #f="ngForm">
            <div class="field">
              <label for="name">Full name</label>
              <input id="name" class="input" name="name" autocomplete="name" required [(ngModel)]="name" />
            </div>
            <div class="field">
              <label for="email">Work email</label>
              <input id="email" class="input" type="email" name="email" autocomplete="email" required email [(ngModel)]="email" />
            </div>
            <div class="field">
              <label for="password">Password</label>
              <input id="password" class="input" type="password" name="password" autocomplete="new-password" required minlength="10" [(ngModel)]="password" aria-describedby="pw-hint" />
              <span id="pw-hint" class="hint">At least 10 characters.</span>
            </div>
            <div class="field">
              <label for="reason">Why do you need access? <span class="muted">(optional)</span></label>
              <textarea id="reason" class="textarea" style="min-height:90px;font-family:var(--font)" name="reason" [(ngModel)]="reason"></textarea>
            </div>
            <button class="btn btn-primary" type="submit" [disabled]="loading() || !f.valid">
              {{ loading() ? 'Sending…' : 'Request access' }}
            </button>
          </form>

          <p class="auth-foot">Already approved? <a routerLink="/login">Sign in</a></p>
        }
      </section>
    </div>
  `,
})
export class RequestAccessComponent {
  private auth = inject(AuthService);

  name = '';
  email = '';
  password = '';
  reason = '';
  loading = signal(false);
  error = signal<string | null>(null);
  done = signal<string | null>(null);

  submit(): void {
    this.loading.set(true);
    this.error.set(null);
    this.auth.requestAccess({ name: this.name, email: this.email, password: this.password, reason: this.reason }).subscribe({
      next: res => this.done.set(res.message),
      error: err => {
        this.error.set(errorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
