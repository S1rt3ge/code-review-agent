"""Pydantic v2 schemas for API request and response validation.

Classes:
    UserCreate: Schema for creating a new user.
    UserResponse: Schema for returning user data.
    ReviewCreate: Schema for creating a review via webhook or manual input.
    ReviewResponse: Full review data including findings and agent executions.
    ReviewListItem: Abbreviated review data for list endpoints.
    ReviewListResponse: Paginated list of reviews.
    FindingSchema: Single finding produced by an agent.
    AgentExecutionSchema: Execution metadata for one agent.
    SettingsResponse: Current user LLM and agent settings.
    SettingsUpdate: Request body for updating settings.
    SettingsTestResponse: LLM connectivity test results.
    DashboardStatsResponse: Aggregate statistics for the dashboard.
    WebhookPayload: GitHub webhook event payload.
    CreateReviewRequest: Manual review creation request.
    PostCommentRequest: Request to post findings as a PR comment.
    PostCommentResponse: Response after posting a PR comment.
    AnalyzeResponse: Response after triggering analysis.
    RepositoryResponse: Single repository record.
    CreateRepositoryRequest: Request body for adding a repository.
    RepositoryListResponse: List of repositories with count.
    HealthResponse: Health check response.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """Request body for user registration."""

    email: str
    password: str
    username: str | None = None


class LoginRequest(BaseModel):
    """Request body for email/password login."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """Response returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    username: str


class PasswordResetRequest(BaseModel):
    """Request password reset for an account email."""

    email: str


class PasswordResetConfirmRequest(BaseModel):
    """Confirm password reset with token and new password."""

    token: str
    new_password: str


class EmailVerificationRequest(BaseModel):
    """Request email verification email."""

    email: str


class EmailVerificationConfirmRequest(BaseModel):
    """Confirm account email verification token."""

    token: str


class MessageResponse(BaseModel):
    """Simple API response with a message."""

    message: str


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Schema for creating a new user account."""

    email: str
    username: str
    plan: str = "free"


class UserResponse(BaseModel):
    """Schema for returning user data (no sensitive fields)."""

    id: UUID
    email: str
    username: str
    plan: str
    email_verified: bool
    email_verified_at: datetime | None = None
    ollama_enabled: bool
    ollama_host: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------


class FindingSchema(BaseModel):
    """Single finding produced by an analysis agent."""

    id: UUID
    review_id: UUID
    agent_name: str
    finding_type: str
    severity: str
    file_path: str
    line_number: int
    message: str
    suggestion: str | None = None
    code_snippet: str | None = None
    category: str | None = None
    is_duplicate: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Agent Execution
# ---------------------------------------------------------------------------


class AgentExecutionSchema(BaseModel):
    """Execution metadata for one agent run."""

    id: UUID
    review_id: UUID
    agent_name: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    tokens_input: int = 0
    tokens_output: int = 0
    findings_count: int = 0
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


class ReviewCreate(BaseModel):
    """Schema for creating a review record (internal use)."""

    user_id: UUID
    repo_id: UUID
    github_pr_number: int
    github_pr_title: str | None = None
    head_sha: str | None = None
    base_sha: str | None = None
    selected_agents: list[str] | None = None


class ReviewResponse(BaseModel):
    """Full review data including findings and agent executions."""

    id: UUID
    user_id: UUID
    repo_id: UUID
    github_pr_number: int
    github_pr_title: str | None = None
    head_sha: str | None = None
    base_sha: str | None = None
    status: str
    error_message: str | None = None
    selected_agents: list[str] | None = None
    lm_used: str | None = None
    total_findings: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    estimated_cost: Decimal = Decimal("0")
    pr_comment_id: int | None = None
    pr_comment_posted: bool = False
    created_at: datetime
    completed_at: datetime | None = None
    findings: list[FindingSchema] = Field(default_factory=list)
    agent_executions: list[AgentExecutionSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ReviewListItem(BaseModel):
    """Abbreviated review data for list endpoints."""

    id: UUID
    repo_id: UUID
    github_pr_number: int
    github_pr_title: str | None = None
    status: str
    total_findings: int = 0
    lm_used: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ReviewListResponse(BaseModel):
    """Paginated list of reviews."""

    reviews: list[ReviewListItem]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class SettingsResponse(BaseModel):
    """Current user LLM and agent settings."""

    plan: str
    api_key_claude_set: bool
    api_key_gpt_set: bool
    ollama_enabled: bool
    ollama_host: str | None = None
    default_agents: list[str] = Field(
        default_factory=lambda: ["security", "performance", "style", "logic"],
    )
    lm_preference: str = "auto"
    warnings: list[str] = Field(default_factory=list)


class SettingsUpdate(BaseModel):
    """Request body for updating user LLM settings."""

    api_key_claude: str | None = None
    api_key_gpt: str | None = None
    ollama_enabled: bool | None = None
    ollama_host: str | None = None
    default_agents: list[str] | None = None
    lm_preference: str | None = None


class SettingsTestResponse(BaseModel):
    """LLM connectivity test results."""

    claude_available: bool = False
    gpt_available: bool = False
    ollama_available: bool = False
    selected: str | None = None
    models: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class DashboardStatsResponse(BaseModel):
    """Aggregate statistics for the dashboard."""

    total_reviews: int = 0
    reviews_today: int = 0
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    findings_by_agent: dict[str, int] = Field(default_factory=dict)
    top_issues: list[dict[str, int | str]] = Field(default_factory=list)
    avg_review_time_seconds: float = 0.0
    tokens_used_this_month: int = 0
    estimated_cost_this_month: Decimal = Decimal("0")
    queue_metrics: dict[str, int | float | None] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# GitHub Webhook
# ---------------------------------------------------------------------------


class _GitRef(BaseModel):
    sha: str


class _PullRequestUser(BaseModel):
    login: str


class _PullRequest(BaseModel):
    number: int
    title: str = ""
    head: _GitRef
    base: _GitRef
    user: _PullRequestUser | None = None


class _RepoOwner(BaseModel):
    login: str


class _Repository(BaseModel):
    owner: _RepoOwner
    name: str
    full_name: str = ""


class WebhookPayload(BaseModel):
    """GitHub webhook event payload for pull_request events."""

    action: str
    pull_request: _PullRequest
    repository: _Repository
    installation: dict | None = None


# ---------------------------------------------------------------------------
# Manual review creation
# ---------------------------------------------------------------------------


class CreateReviewRequest(BaseModel):
    """Request body for manually creating a review."""

    repo_id: UUID
    github_pr_number: int
    selected_agents: list[str] = Field(
        default_factory=lambda: ["security", "performance", "style", "logic"],
    )
    code_diff: str | None = None
    context: str | None = None


# ---------------------------------------------------------------------------
# PR comment
# ---------------------------------------------------------------------------


class PostCommentRequest(BaseModel):
    """Request body for posting findings as a PR comment."""

    format: str = "critical_first"
    include_agent_names: bool = True


class PostCommentResponse(BaseModel):
    """Response after posting a PR comment."""

    comment_id: int
    url: str
    posted_at: datetime


# ---------------------------------------------------------------------------
# Analysis trigger
# ---------------------------------------------------------------------------


class AnalyzeResponse(BaseModel):
    """Response after triggering review analysis."""

    review_id: UUID
    status: str


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------


class RepositoryResponse(BaseModel):
    """Single repository record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    github_repo_owner: str
    github_repo_name: str
    github_repo_url: str
    github_installation_id: int | None
    enabled: bool
    created_at: datetime


class CreateRepositoryRequest(BaseModel):
    """Request body for adding a new repository."""

    github_repo_owner: str = Field(
        ..., min_length=1, max_length=100, description="GitHub owner (user or org)"
    )
    github_repo_name: str = Field(
        ..., min_length=1, max_length=100, description="Repository name"
    )


class RepositoryListResponse(BaseModel):
    """List of repositories with total count."""

    repositories: list[RepositoryResponse]
    total: int


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    environment: str
    database: str
    queue: dict[str, int | float | None] = Field(default_factory=dict)
