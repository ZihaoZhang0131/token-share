export type Role = "admin" | "user";

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  must_change_password: boolean;
  active: boolean;
  monthly_token_limit: number;
  rpm_limit: number;
  tpm_limit: number;
  allowed_models: string[];
  created_at: string;
}

export interface Session {
  user: User;
  csrf_token: string;
}

export interface Provider {
  id: string;
  name: string;
  base_url: string;
  key_last4: string;
  timeout_seconds: number;
  supports_stream_usage: boolean;
  active: boolean;
  created_at: string;
}

export interface ModelRoute {
  id: string;
  public_name: string;
  upstream_model: string;
  provider_id: string;
  max_output_tokens: number;
  tokenizer: string;
  active: boolean;
  created_at: string;
}

export interface AccessKey {
  id: string;
  name: string;
  prefix: string;
  last4: string;
  rpm_limit: number;
  tpm_limit: number;
  active: boolean;
  last_used_at: string | null;
  created_at: string;
}

export interface Usage {
  month: string;
  used_tokens: number;
  remaining_tokens: number;
  monthly_token_limit: number;
  request_count: number;
  input_tokens: number;
  output_tokens: number;
  daily: { date: string; tokens: number }[];
}

export interface UsageLog {
  request_id: string;
  user_id: string;
  access_key_id: string;
  model_alias: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  status_code: number;
  latency_ms: number;
  error_type: string | null;
  created_at: string;
}

export interface DashboardStats {
  period_days: number;
  requests: number;
  tokens: number;
  success_rate: number;
  avg_latency_ms: number;
  users: number;
  providers: number;
  models: number;
}
