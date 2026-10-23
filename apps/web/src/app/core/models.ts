export interface Candidate {
  id: number;
  name: string;
  number: string;
  subscription: string;
  is_active: boolean;
  email: string;
  email_subject: string;
  email_body: string;
  resume: string | null;
  tag: string;
  owner_id: number | null;
  owner_email: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CandidateInput {
  name: string;
  number: string;
  subscription: string;
  is_active: boolean;
  email: string;
  email_password: string;
  tag: string;
  email_subject: string;
  email_body: string;
  resume_file: File | null;
}

export interface CountRow {
  label: string;
  count: number;
}

export interface DashboardStats {
  total: number;
  tag_count: number;
  by_tag: { tag: string; count: number }[];
  by_date: { date: string; count: number }[];
}

export interface LoginResponse {
  token: string;
  user: AppUser;
}

export type Role = 'super_admin' | 'admin' | 'user';
export type AccountStatus = 'pending' | 'active' | 'rejected' | 'disabled';

export interface AppUser {
  id: number;
  email: string;
  name: string;
  role: Role;
  status: AccountStatus;
  request_reason: string | null;
  last_login_at: string | null;
  created_at: string | null;
  reviewed_at: string | null;
  can_manage?: boolean;
  assignable_roles?: Role[];
}

export interface Invitation {
  id: number;
  email: string;
  role: Role;
  created_at: string | null;
  expires_at: string;
  expired: boolean;
  can_manage: boolean;
}

export interface InvitationResult {
  invitation: Invitation;
  invite_url: string;
  email_sent: boolean;
}

export const ROLE_LABELS: Record<Role, string> = {
  super_admin: 'Super admin',
  admin: 'Admin',
  user: 'User',
};

export interface TagUsage {
  jobs: number;
  candidates: number;
  email_records: number;
}

export interface TagOption {
  id: number;
  name: string;
  label: string;
  description: string | null;
  is_active: boolean;
  usage?: TagUsage;
}

export interface RunLogEntry {
  id: number;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  records_count: number | null;
  error_message: string | null;
}

export interface ScrapeJob {
  id: number;
  keyword: string;
  scroll_count: number;
  tag: string;
  cron_expression: string;
  status: 'idle' | 'running' | 'completed' | 'error' | 'hold';
  on_hold: boolean;
  created_at: string | null;
  updated_at: string | null;
  last_run: RunLogEntry | null;
  email_count: number;
  warning?: string | null;
}

export interface ScrapeJobInput {
  keyword: string;
  scroll_count: number;
  tag: string;
  cron_expression: string;
}
