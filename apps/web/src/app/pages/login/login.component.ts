import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth.service';
import { errorMessage } from '../../core/error-message';
import { IconComponent } from '../../shared/icon.component';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, RouterLink, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="auth-page">
      <section class="card auth-card" aria-labelledby="login-title">
        <div class="auth-brand"><span class="mark"><app-icon name="shield" [size]="20" /></span> LinkedIn Scraper Console</div>
        <div>
          <h1 id="login-title">Sign in</h1>
          <p class="muted">Access is by invitation or admin approval only.</p>
        </div>

        @if (error()) {
          <div class="alert alert-error" role="alert"><app-icon name="alert" [size]="18" /> {{ error() }}</div>
        }

        <form (ngSubmit)="submit()" #f="ngForm">
          <div class="field">
            <label for="email">Email</label>
            <input id="email" class="input" type="email" name="email" autocomplete="username" required [(ngModel)]="email" />
          </div>
          <div class="field">
            <label for="password">Password</label>
            <input id="password" class="input" type="password" name="password" autocomplete="current-password" required [(ngModel)]="password" />
          </div>
          <button class="btn btn-primary" type="submit" [disabled]="loading() || !f.valid">
            {{ loading() ? 'Signing in…' : 'Sign in' }}
          </button>
        </form>

        <p class="auth-foot">No account? <a routerLink="/request-access">Request access</a></p>
      </section>
    </div>
  `,
})
export class LoginComponent {
  private auth = inject(AuthService);
  private router = inject(Router);

  email = '';
  password = '';
  loading = signal(false);
  error = signal<string | null>(null);

  submit(): void {
    this.loading.set(true);
    this.error.set(null);
    this.auth.login(this.email, this.password).subscribe({
      next: () => this.router.navigate(['/dashboard']),
      error: err => {
        this.error.set(errorMessage(err, 'Invalid email or password'));
        this.loading.set(false);
      },
    });
  }
}
