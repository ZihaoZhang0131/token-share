from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import Role


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserView(ORMModel):
    id: str
    # Validate emails on writes, not while serializing historical database rows.
    # One legacy/imported address must not take down the whole admin user list.
    email: str
    display_name: str
    role: Role
    must_change_password: bool
    active: bool
    monthly_token_limit: int
    rpm_limit: int
    tpm_limit: int
    allowed_models: List[str]
    created_at: datetime


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class SessionView(BaseModel):
    user: UserView
    csrf_token: str


class PasswordChangeInput(BaseModel):
    current_password: str
    new_password: str


class AdminUserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    temporary_password: str
    monthly_token_limit: int = Field(gt=0)
    rpm_limit: int = Field(ge=1, le=10000)
    tpm_limit: int = Field(ge=100, le=100_000_000)
    allowed_models: List[str] = Field(default_factory=list)


class AdminUserUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    monthly_token_limit: Optional[int] = Field(default=None, gt=0)
    rpm_limit: Optional[int] = Field(default=None, ge=1, le=10000)
    tpm_limit: Optional[int] = Field(default=None, ge=100, le=100_000_000)
    allowed_models: Optional[List[str]] = None
    active: Optional[bool] = None


class PasswordResetInput(BaseModel):
    temporary_password: str


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(min_length=8, max_length=500)
    api_key: str = Field(min_length=4, max_length=1000)
    timeout_seconds: int = Field(default=120, ge=10, le=600)
    supports_stream_usage: bool = False


class ProviderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    base_url: Optional[str] = Field(default=None, min_length=8, max_length=500)
    api_key: Optional[str] = Field(default=None, min_length=4, max_length=1000)
    timeout_seconds: Optional[int] = Field(default=None, ge=10, le=600)
    supports_stream_usage: Optional[bool] = None
    active: Optional[bool] = None


class ProviderView(ORMModel):
    id: str
    name: str
    base_url: str
    key_last4: str
    timeout_seconds: int
    supports_stream_usage: bool
    active: bool
    created_at: datetime


class ModelCreate(BaseModel):
    public_name: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,120}$")
    upstream_model: str = Field(min_length=1, max_length=200)
    provider_id: str
    max_output_tokens: int = Field(default=4096, ge=1, le=262144)
    tokenizer: str = Field(default="cl100k_base", min_length=1, max_length=50)
    api_mode: Literal["chat", "responses", "both"] = "chat"
    reasoning_effort: Optional[
        Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]
    ] = None


class ModelUpdate(BaseModel):
    public_name: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9._:-]{1,120}$")
    upstream_model: Optional[str] = Field(default=None, min_length=1, max_length=200)
    provider_id: Optional[str] = None
    max_output_tokens: Optional[int] = Field(default=None, ge=1, le=262144)
    tokenizer: Optional[str] = Field(default=None, min_length=1, max_length=50)
    active: Optional[bool] = None
    api_mode: Optional[Literal["chat", "responses", "both"]] = None
    reasoning_effort: Optional[
        Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]
    ] = None


class ModelView(ORMModel):
    id: str
    public_name: str
    upstream_model: str
    provider_id: str
    max_output_tokens: int
    tokenizer: str
    api_mode: str
    reasoning_effort: Optional[str]
    active: bool
    created_at: datetime


class AccessKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    rpm_limit: int = Field(ge=1, le=10000)
    tpm_limit: int = Field(ge=100, le=100_000_000)


class AccessKeyView(ORMModel):
    id: str
    name: str
    prefix: str
    last4: str
    rpm_limit: int
    tpm_limit: int
    active: bool
    last_used_at: Optional[datetime]
    created_at: datetime


class AccessKeyCreated(BaseModel):
    key: AccessKeyView
    plaintext: str


class UsageSummary(BaseModel):
    month: str
    used_tokens: int
    remaining_tokens: int
    monthly_token_limit: int
    request_count: int
    input_tokens: int
    output_tokens: int
    daily: List[Dict[str, Any]]


AnalyticsPeriod = Literal["month", "7d", "30d"]


class AnalyticsCounts(BaseModel):
    requests: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    successes: int
    failures: int
    avg_latency_ms: Optional[float]


class AnalyticsSummary(AnalyticsCounts):
    success_rate: Optional[float]


class AnalyticsDay(AnalyticsCounts):
    date: str


class AnalyticsRank(BaseModel):
    id: str
    label: str
    total_tokens: int
    requests: int


class AnalyticsView(BaseModel):
    period: AnalyticsPeriod
    start: datetime
    end: datetime
    timezone: str
    summary: AnalyticsSummary
    daily: List[AnalyticsDay]
    models: List[AnalyticsRank]


class AdminAnalyticsView(AnalyticsView):
    users: List[AnalyticsRank]


class AuditView(ORMModel):
    id: str
    actor_user_id: str
    action: str
    target_type: str
    target_id: str
    metadata_json: Dict[str, Any]
    created_at: datetime


class UsageLogView(ORMModel):
    request_id: str
    user_id: str
    access_key_id: str
    model_alias: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    status_code: int
    latency_ms: int
    error_type: Optional[str]
    created_at: datetime


class OpenAIError(BaseModel):
    message: str
    type: str
    param: Optional[str] = None
    code: Optional[str] = None


class OpenAIErrorEnvelope(BaseModel):
    error: OpenAIError


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = Field(min_length=1, max_length=120)
    messages: List[Dict[str, Any]] = Field(min_length=1)
    stream: bool = False
    max_tokens: Optional[int] = Field(default=None, ge=1)
    max_completion_tokens: Optional[int] = Field(default=None, ge=1)
    stream_options: Optional[Dict[str, Any]] = None

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, value):
        for item in value:
            if not isinstance(item, dict) or "role" not in item:
                raise ValueError("each message must contain role")
        return value


class ResponsesRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = Field(min_length=1, max_length=120)
    input: Union[str, List[Dict[str, Any]]]
    instructions: Optional[str] = None
    stream: bool = False
    max_output_tokens: Optional[int] = Field(default=None, ge=1)
