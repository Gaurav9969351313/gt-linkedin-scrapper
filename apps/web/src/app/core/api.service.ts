import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  AccountStatus,
  AppUser,
  Candidate,
  CandidateInput,
  DashboardStats,
  Invitation,
  InvitationResult,
  Role,
  RunLogEntry,
  ScrapeJob,
  ScrapeJobInput,
  TagOption,
} from './models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);

  // ---------- dashboard & candidates ----------

  getStats(): Observable<DashboardStats> {
    return this.http.get<DashboardStats>('/api/dashboard/stats');
  }

  /** Active tags, for choosing a tag on candidates and jobs. */
  getTags(): Observable<TagOption[]> {
    return this.http.get<TagOption[]>('/api/tags');
  }

  getCandidates(tag?: string): Observable<Candidate[]> {
    const params = tag ? new HttpParams().set('tag', tag) : undefined;
    return this.http.get<Candidate[]>('/api/candidates', { params });
  }

  /** The signed-in account's own candidate, or null. */
  getMyCandidate(): Observable<Candidate | null> {
    return this.http.get<Candidate | null>('/api/candidates/mine');
  }

  createCandidate(input: CandidateInput): Observable<Candidate> {
    return this.http.post<Candidate>('/api/candidates', this.toFormData(input));
  }

  updateCandidate(id: number, input: CandidateInput): Observable<Candidate> {
    return this.http.put<Candidate>(`/api/candidates/${id}`, this.toFormData(input));
  }

  deleteCandidate(id: number): Observable<void> {
    return this.http.delete<void>(`/api/candidates/${id}`);
  }

  // ---------- user administration ----------

  getUsers(status?: AccountStatus): Observable<AppUser[]> {
    const params = status ? new HttpParams().set('status', status) : undefined;
    return this.http.get<AppUser[]>('/api/users', { params });
  }

  approveUser(id: number, role: Role): Observable<AppUser> {
    return this.http.post<AppUser>(`/api/users/${id}/approve`, { role });
  }

  rejectUser(id: number): Observable<AppUser> {
    return this.http.post<AppUser>(`/api/users/${id}/reject`, {});
  }

  disableUser(id: number): Observable<AppUser> {
    return this.http.post<AppUser>(`/api/users/${id}/disable`, {});
  }

  enableUser(id: number): Observable<AppUser> {
    return this.http.post<AppUser>(`/api/users/${id}/enable`, {});
  }

  changeRole(id: number, role: Role): Observable<AppUser> {
    return this.http.patch<AppUser>(`/api/users/${id}/role`, { role });
  }

  getInvitations(): Observable<Invitation[]> {
    return this.http.get<Invitation[]>('/api/invitations');
  }

  invite(email: string, role: Role): Observable<InvitationResult> {
    return this.http.post<InvitationResult>('/api/invitations', { email, role });
  }

  resendInvitation(id: number): Observable<InvitationResult> {
    return this.http.post<InvitationResult>(`/api/invitations/${id}/resend`, {});
  }

  revokeInvitation(id: number): Observable<void> {
    return this.http.delete<void>(`/api/invitations/${id}`);
  }

  // ---------- tag management (super admin) ----------

  getAllTags(): Observable<TagOption[]> {
    return this.http.get<TagOption[]>('/api/admin/tags');
  }

  createTag(body: { name: string; label: string; description: string | null }): Observable<TagOption> {
    return this.http.post<TagOption>('/api/admin/tags', body);
  }

  updateTag(id: number, body: { label: string; description: string | null; is_active: boolean }): Observable<TagOption> {
    return this.http.put<TagOption>(`/api/admin/tags/${id}`, body);
  }

  deleteTag(id: number): Observable<void> {
    return this.http.delete<void>(`/api/admin/tags/${id}`);
  }

  // ---------- scrape job management (super admin) ----------

  getJobs(): Observable<ScrapeJob[]> {
    return this.http.get<ScrapeJob[]>('/api/admin/jobs');
  }

  createJob(body: ScrapeJobInput): Observable<ScrapeJob> {
    return this.http.post<ScrapeJob>('/api/admin/jobs', body);
  }

  updateJob(id: number, body: ScrapeJobInput): Observable<ScrapeJob> {
    return this.http.put<ScrapeJob>(`/api/admin/jobs/${id}`, body);
  }

  holdJob(id: number): Observable<ScrapeJob> {
    return this.http.post<ScrapeJob>(`/api/admin/jobs/${id}/hold`, {});
  }

  resumeJob(id: number): Observable<ScrapeJob> {
    return this.http.post<ScrapeJob>(`/api/admin/jobs/${id}/resume`, {});
  }

  runJob(id: number): Observable<{ flow_run_id: string; detail: string }> {
    return this.http.post<{ flow_run_id: string; detail: string }>(`/api/admin/jobs/${id}/run`, {});
  }

  getJobRuns(id: number): Observable<RunLogEntry[]> {
    return this.http.get<RunLogEntry[]>(`/api/admin/jobs/${id}/runs`);
  }

  deleteJob(id: number): Observable<{ warning: string | null }> {
    return this.http.delete<{ warning: string | null }>(`/api/admin/jobs/${id}`);
  }

  private toFormData(input: CandidateInput): FormData {
    const data = new FormData();
    for (const [key, value] of Object.entries(input)) {
      if (key === 'resume_file') {
        if (value) data.append(key, value as File);
      } else {
        data.append(key, String(value));
      }
    }
    return data;
  }
}
