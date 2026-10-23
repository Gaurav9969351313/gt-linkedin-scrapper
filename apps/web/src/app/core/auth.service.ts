import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';

import { AppUser, LoginResponse } from './models';

const TOKEN_KEY = 'gt_web_token';
const USER_KEY = 'gt_web_user';

function readStorage(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function readUser(): AppUser | null {
  try {
    const raw = readStorage(USER_KEY);
    return raw ? (JSON.parse(raw) as AppUser) : null;
  } catch {
    return null;
  }
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);

  readonly token = signal<string | null>(readStorage(TOKEN_KEY));
  readonly user = signal<AppUser | null>(readUser());
  readonly isAuthenticated = computed(() => !!this.token());
  readonly isAdmin = computed(() => ['admin', 'super_admin'].includes(this.user()?.role ?? ''));
  readonly isSuperAdmin = computed(() => this.user()?.role === 'super_admin');

  login(email: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>('/api/auth/login', { email, password }).pipe(tap(res => this.setSession(res)));
  }

  requestAccess(body: { name: string; email: string; password: string; reason: string }) {
    return this.http.post<{ status: string; message: string }>('/api/auth/request-access', body);
  }

  lookupInvitation(token: string) {
    return this.http.get<{ email: string; role: string }>('/api/invitations/lookup', { params: { token } });
  }

  acceptInvitation(token: string, name: string, password: string): Observable<LoginResponse> {
    return this.http
      .post<LoginResponse>('/api/invitations/accept', { token, name, password })
      .pipe(tap(res => this.setSession(res)));
  }

  /** Refreshes role/status from the server (e.g. after an admin changed them). */
  refreshMe(): Observable<AppUser> {
    return this.http.get<AppUser>('/api/auth/me').pipe(tap(user => this.storeUser(user)));
  }

  logout(): void {
    this.token.set(null);
    this.user.set(null);
    try {
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(USER_KEY);
    } catch {
      /* ignore */
    }
    this.router.navigate(['/login']);
  }

  private setSession(res: LoginResponse): void {
    this.token.set(res.token);
    try {
      sessionStorage.setItem(TOKEN_KEY, res.token);
    } catch {
      /* storage unavailable: session lasts until reload */
    }
    this.storeUser(res.user);
  }

  private storeUser(user: AppUser): void {
    this.user.set(user);
    try {
      sessionStorage.setItem(USER_KEY, JSON.stringify(user));
    } catch {
      /* ignore */
    }
  }
}
