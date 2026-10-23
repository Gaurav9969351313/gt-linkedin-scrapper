import { ChangeDetectionStrategy, Component, OnInit, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../core/auth.service';
import { ROLE_LABELS } from '../core/models';
import { IconComponent } from '../shared/icon.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
})
export class ShellComponent implements OnInit {
  auth = inject(AuthService);

  roleLabel = computed(() => {
    const role = this.auth.user()?.role;
    return role ? ROLE_LABELS[role] : '';
  });

  // Admins manage every candidate; users only see their own.
  nav = computed(() =>
    this.auth.isAdmin()
      ? [
          { path: '/dashboard', label: 'Dashboard', icon: 'dashboard' },
          { path: '/candidates', label: 'Candidates', icon: 'users' },
          // Scraper configuration is super admin only.
          ...(this.auth.isSuperAdmin()
            ? [
                { path: '/jobs', label: 'Scraper jobs', icon: 'search' },
                { path: '/tags', label: 'Tags', icon: 'tag' },
              ]
            : []),
          { path: '/users', label: 'Users', icon: 'shield' },
        ]
      : [
          { path: '/dashboard', label: 'Dashboard', icon: 'dashboard' },
          { path: '/my-candidature', label: 'My Candidature', icon: 'file' },
        ],
  );

  ngOnInit(): void {
    // Picks up role changes made by an admin since this session started.
    this.auth.refreshMe().subscribe({ error: () => {} });
  }
}
