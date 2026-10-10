import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

class Owned(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        abstract = True

class AssistantState(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    paused = models.BooleanField(default=False)
    scheduler_heartbeat_at = models.DateTimeField(null=True)

class Conversation(Owned):
    title = models.CharField(max_length=160)

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, related_name="messages", on_delete=models.CASCADE)
    role = models.CharField(max_length=16)
    content = models.TextField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["created_at", "id"]

class Workflow(Owned):
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    steps = models.JSONField(default=list)
    allowed_tools = models.JSONField(default=list)
    allowed_domains = models.JSONField(default=list)
    allowed_paths = models.JSONField(default=list)
    trigger = models.JSONField(default=dict)
    enabled = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    reviewed_at = models.DateTimeField(null=True, blank=True)

class WorkflowRun(Owned):
    workflow = models.ForeignKey(Workflow, on_delete=models.SET_NULL, null=True)
    snapshot = models.JSONField(default=dict)
    status = models.CharField(max_length=32, default="queued")
    step_index = models.PositiveIntegerField(default=0)
    results = models.JSONField(default=list)
    error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    execution_started_at = models.DateTimeField(null=True)

class Approval(Owned):
    run = models.ForeignKey(WorkflowRun, on_delete=models.CASCADE, related_name="approvals")
    step_index = models.PositiveIntegerField()
    risk = models.CharField(max_length=40)
    description = models.TextField()
    payload_digest = models.CharField(max_length=64)
    status = models.CharField(max_length=16, default="pending")
    expires_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True)

class ScheduledTask(Owned):
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=32, default="reminder")
    payload = models.JSONField(default=dict)
    schedule = models.JSONField(default=dict)
    next_run_at = models.DateTimeField(null=True)
    enabled = models.BooleanField(default=True)

class ScheduledOccurrence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(ScheduledTask, on_delete=models.CASCADE)
    scheduled_for = models.DateTimeField()
    status = models.CharField(max_length=24, default="pending")
    started_at = models.DateTimeField(null=True)
    result = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["task", "scheduled_for"], name="unique_task_occurrence")]

class DesktopDevice(Owned):
    name = models.CharField(max_length=120)
    token_digest = models.CharField(max_length=64, unique=True)
    last_seen_at = models.DateTimeField(null=True)
    revoked = models.BooleanField(default=False)

class DesktopJob(Owned):
    run = models.ForeignKey(WorkflowRun, on_delete=models.CASCADE, related_name="desktop_jobs")
    step_index = models.PositiveIntegerField()
    tool = models.CharField(max_length=80)
    args = models.JSONField(default=dict)
    policy = models.JSONField(default=dict)
    status = models.CharField(max_length=32, default="queued")
    approved_risk = models.CharField(max_length=40, null=True)
    device = models.ForeignKey(DesktopDevice, on_delete=models.SET_NULL, null=True)
    lease_digest = models.CharField(max_length=64, blank=True)
    lease_expires_at = models.DateTimeField(null=True)
    result = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "step_index"], name="unique_run_desktop_step")]

class Report(Owned):
    title = models.CharField(max_length=240)
    status = models.CharField(max_length=24, default="queued")
    content = models.JSONField(default=dict)
    citations = models.JSONField(default=list)
    docx = models.FileField(upload_to="reports/%Y/%m/", blank=True)
    pdf = models.FileField(upload_to="reports/%Y/%m/", blank=True)
    error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

class AuditEvent(Owned):
    event = models.CharField(max_length=100)
    detail = models.JSONField(default=dict)
    class Meta:
        ordering = ["-created_at"]

class ProviderCredential(Owned):
    provider = models.CharField(max_length=30)
    ciphertext = models.TextField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "provider"], name="unique_provider_credential")]

class OAuthState(Owned):
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()

class UsageDay(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.localdate)
    model_calls = models.PositiveIntegerField(default=0)
    input_chars = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "date"], name="unique_daily_usage")]

class Notification(Owned):
    text = models.TextField()
    status = models.CharField(max_length=24, default="pending")
    started_at = models.DateTimeField(null=True)
    error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True)

class TelegramUpdate(models.Model):
    update_id = models.BigIntegerField(primary_key=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=24, default="pending")
    started_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
