import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

class RoadmapBoard(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    items = models.JSONField(default=list)
    version = models.PositiveIntegerField(default=1)


class DesktopLaunchGrant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    digest = models.CharField(max_length=64, unique=True)
    token_digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    consumed = models.BooleanField(default=False)


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
    telegram_offset = models.BigIntegerField(default=0)

class Conversation(Owned):
    title = models.CharField(max_length=160)
    model_profile = models.CharField(max_length=24, default="configured")

class AssistantPreferences(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    interactive_profile = models.CharField(max_length=24, default="gemini")
    telegram_voice_replies = models.BooleanField(default=False)
    memory_enabled = models.BooleanField(default=True)
    memory_suggestions = models.BooleanField(default=True)
    response_detail = models.CharField(max_length=12, default="auto", choices=[(value, value) for value in ("auto", "brief", "balanced", "detailed")])

class PersonalMemory(Owned):
    key = models.CharField(max_length=100)
    title = models.CharField(max_length=100)
    content = models.CharField(max_length=500)
    fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=16, default="suggested")
    pinned = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    source_message = models.ForeignKey("Message", null=True, blank=True, on_delete=models.CASCADE)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "fingerprint"], name="unique_owner_memory_fact"),
            models.UniqueConstraint(fields=["user", "key"], condition=models.Q(status="active"), name="unique_active_memory_key"),
        ]
        indexes = [models.Index(fields=["user", "status", "updated_at"], name="owner_memory_lookup")]

class MemoryTerm(models.Model):
    memory = models.ForeignKey(PersonalMemory, related_name="terms", on_delete=models.CASCADE)
    token = models.CharField(max_length=40, db_index=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["memory", "token"], name="unique_memory_term")]

class ForgottenMemory(Owned):
    fingerprint = models.CharField(max_length=64)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "fingerprint"], name="unique_forgotten_memory")]

class ChannelSession(Owned):
    channel = models.CharField(max_length=24)
    external_key = models.CharField(max_length=100)
    conversation = models.ForeignKey(Conversation, null=True, on_delete=models.SET_NULL)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "channel", "external_key"], name="unique_channel_session")]

class Command(Owned):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="commands")
    channel = models.CharField(max_length=24, default="web")
    request_id = models.CharField(max_length=128)
    input_mode = models.CharField(max_length=12, default="text")
    input_text = models.TextField()
    fingerprint = models.CharField(max_length=64)
    model_profile = models.CharField(max_length=24, default="configured")
    status = models.CharField(max_length=32, default="queued")
    response = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "channel", "request_id"], name="unique_channel_command")]

class CommandEvent(models.Model):
    command = models.ForeignKey(Command, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=32)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

class CommandCancellation(Owned):
    channel = models.CharField(max_length=24, default="web")
    request_id = models.CharField(max_length=128)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "channel", "request_id"], name="unique_cancelled_request")]

class FormRequest(Owned):
    kind = models.CharField(max_length=32)
    request_id = models.CharField(max_length=128)
    fingerprint = models.CharField(max_length=64)
    resource_id = models.UUIDField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "kind", "request_id"], name="unique_form_request")]

class ActionExecution(Owned):
    command = models.ForeignKey(Command, on_delete=models.CASCADE, related_name="actions")
    step = models.PositiveIntegerField()
    tool = models.CharField(max_length=80)
    args = models.JSONField(default=dict)
    status = models.CharField(max_length=32, default="pending")
    result = models.JSONField(default=dict)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["command", "step"], name="unique_command_action")]

class ActionProposal(Owned):
    action = models.OneToOneField(ActionExecution, on_delete=models.CASCADE, related_name="proposal")
    revision = models.PositiveIntegerField(default=1)
    payload_digest = models.CharField(max_length=64)
    readback = models.TextField()
    status = models.CharField(max_length=24, default="pending")
    expires_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True)

class Delivery(Owned):
    command = models.ForeignKey(Command, on_delete=models.CASCADE, related_name="deliveries")
    position = models.PositiveIntegerField()
    destination = models.CharField(max_length=100)
    text = models.TextField()
    status = models.CharField(max_length=24, default="pending")
    provider_message_id = models.CharField(max_length=100, blank=True)
    due_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True)
    sent_at = models.DateTimeField(null=True)
    error = models.TextField(blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["command", "position"], name="unique_command_delivery")]

class ModelHealth(Owned):
    provider = models.CharField(max_length=24)
    model_name = models.CharField(max_length=160)
    last_success_at = models.DateTimeField(null=True)
    last_failure_at = models.DateTimeField(null=True)
    error = models.TextField(blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "provider", "model_name"], name="unique_model_health")]

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
    progress = models.JSONField(default=dict)
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
    read_at = models.DateTimeField(null=True)

class TelegramUpdate(models.Model):
    update_id = models.BigIntegerField(primary_key=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=24, default="pending")
    started_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
