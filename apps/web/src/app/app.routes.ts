import { Routes } from '@angular/router';

import { adminGuard, authGuard, guestGuard, superAdminGuard } from './core/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    title: 'Sign in · LinkedIn Scraper',
    loadComponent: () => import('./pages/login/login.component').then(m => m.LoginComponent),
  },
  {
    path: 'request-access',
    canActivate: [guestGuard],
    title: 'Request access · LinkedIn Scraper',
    loadComponent: () => import('./pages/request-access/request-access.component').then(m => m.RequestAccessComponent),
  },
  {
    path: 'accept-invite',
    title: 'Accept invitation · LinkedIn Scraper',
    loadComponent: () => import('./pages/accept-invite/accept-invite.component').then(m => m.AcceptInviteComponent),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./layout/shell.component').then(m => m.ShellComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        title: 'Dashboard · LinkedIn Scraper',
        loadComponent: () => import('./pages/dashboard/dashboard.component').then(m => m.DashboardComponent),
      },
      {
        path: 'candidates',
        canActivate: [adminGuard],
        title: 'Candidates · LinkedIn Scraper',
        loadComponent: () => import('./pages/candidates/candidates.component').then(m => m.CandidatesComponent),
      },
      {
        path: 'my-candidature',
        title: 'My Candidature · LinkedIn Scraper',
        loadComponent: () => import('./pages/my-candidature/my-candidature.component').then(m => m.MyCandidatureComponent),
      },
      {
        path: 'jobs',
        canActivate: [superAdminGuard],
        title: 'Scraper jobs · LinkedIn Scraper',
        loadComponent: () => import('./pages/jobs/jobs.component').then(m => m.JobsComponent),
      },
      {
        path: 'tags',
        canActivate: [superAdminGuard],
        title: 'Tags · LinkedIn Scraper',
        loadComponent: () => import('./pages/tags/tags.component').then(m => m.TagsComponent),
      },
      {
        path: 'users',
        canActivate: [adminGuard],
        title: 'Users · LinkedIn Scraper',
        loadComponent: () => import('./pages/users/users.component').then(m => m.UsersComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
