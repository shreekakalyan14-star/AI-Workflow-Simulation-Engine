import enum


# ==========================================================
# COMPANY
# ==========================================================

class CompanyType(str, enum.Enum):
    STARTUP = "startup"
    PRODUCT_COMPANY = "product_company"
    MNC = "mnc"
    HEALTHCARE = "healthcare"
    BANKING = "banking"
    ECOMMERCE = "ecommerce"
    EDUCATION = "education"


# ==========================================================
# INTERNSHIP
# ==========================================================

class InternshipStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"


# ==========================================================
# PROJECT
# ==========================================================

class DifficultyLevel(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class ProjectStatus(str, enum.Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProjectPhase(str, enum.Enum):
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    DESIGN = "design"
    DEVELOPMENT = "development"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    MAINTENANCE = "maintenance"


# ==========================================================
# SPRINT
# ==========================================================

class SprintStatus(str, enum.Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"


# ==========================================================
# TASK
# ==========================================================

class TaskStatus(str, enum.Enum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    CHANGES_REQUESTED = "changes_requested"
    MANAGER_APPROVAL = "manager_approval"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ==========================================================
# SUBMISSION
# ==========================================================

class SubmissionStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    REJECTED = "rejected"


class FileType(str, enum.Enum):
    PYTHON = "python"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    REACT = "react"
    HTML = "html"
    CSS = "css"
    JSON = "json"
    ZIP = "zip"
    PDF = "pdf"
    IMAGE = "image"
    DOCUMENT = "document"


# ==========================================================
# REVIEW
# ==========================================================

class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ReviewResult(str, enum.Enum):
    APPROVED = "approved"
    CHANGES_REQUIRED = "changes_required"
    REJECTED = "rejected"


class ReviewSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ==========================================================
# WORKFLOW
# ==========================================================

class WorkflowState(str, enum.Enum):
    NOT_STARTED = "not_started"
    TASK_ASSIGNED = "task_assigned"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    MANAGER_REVIEW = "manager_review"
    COMPLETED = "completed"


# ==========================================================
# MANAGER
# ==========================================================

class ManagerPersonality(str, enum.Enum):
    STRICT = "strict"
    FRIENDLY = "friendly"
    CORPORATE = "corporate"
    STARTUP_FOUNDER = "startup_founder"


# ==========================================================
# AI PERSONAS
# ==========================================================

class AIPersona(str, enum.Enum):
    MANAGER = "manager"
    BACKEND_ENGINEER = "backend_engineer"
    FRONTEND_ENGINEER = "frontend_engineer"
    FULLSTACK_ENGINEER = "fullstack_engineer"
    QA_ENGINEER = "qa_engineer"
    DEVOPS_ENGINEER = "devops_engineer"
    AI_ENGINEER = "ai_engineer"
    SECURITY_ENGINEER = "security_engineer"


# ==========================================================
# CHAT
# ==========================================================

class MessageSenderType(str, enum.Enum):
    STUDENT = "student"
    MANAGER = "manager"
    TEAM_MEMBER = "team_member"
    SYSTEM = "system"


# ==========================================================
# NOTIFICATIONS
# ==========================================================

class NotificationType(str, enum.Enum):
    TASK_ASSIGNED = "task_assigned"
    TASK_SUBMITTED = "task_submitted"
    TASK_APPROVED = "task_approved"
    TASK_REJECTED = "task_rejected"
    CHANGES_REQUESTED = "changes_requested"
    DEADLINE_UPDATED = "deadline_updated"
    MEETING_SCHEDULED = "meeting_scheduled"
    REQUIREMENT_CHANGED = "requirement_changed"
    BUG_REPORTED = "bug_reported"
    SPRINT_STARTED = "sprint_started"
    SPRINT_COMPLETED = "sprint_completed"
    PROJECT_COMPLETED = "project_completed"


# ==========================================================
# EVENTS
# ==========================================================

class EventType(str, enum.Enum):
    REQUIREMENT_CHANGE = "requirement_change"
    CLIENT_FEEDBACK = "client_feedback"
    BUG_REPORT = "bug_report"
    CODE_REVIEW = "code_review"
    SPRINT_PLANNING = "sprint_planning"
    SPRINT_REVIEW = "sprint_review"
    PRODUCTION_FAILURE = "production_failure"
    DATABASE_CHANGE = "database_change"
    SECURITY_AUDIT = "security_audit"
    DEADLINE_CHANGED = "deadline_changed"
    EMERGENCY_MEETING = "emergency_meeting"


# ==========================================================
# MEETINGS
# ==========================================================

class MeetingType(str, enum.Enum):
    DAILY_STANDUP = "daily_standup"
    SPRINT_PLANNING = "sprint_planning"
    SPRINT_REVIEW = "sprint_review"
    RETROSPECTIVE = "retrospective"
    EMERGENCY = "emergency"