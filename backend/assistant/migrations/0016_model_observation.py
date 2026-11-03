import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("assistant", "0015_google_identity"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]  # noqa: RUF012
    operations = [migrations.CreateModel(  # noqa: RUF012
        name="ModelObservation",
        fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("provider", models.CharField(max_length=24)),
            ("model_name", models.CharField(max_length=160)),
            ("operation", models.CharField(max_length=64)),
            ("status", models.CharField(max_length=16)),
            ("error_code", models.CharField(blank=True, max_length=32)),
            ("latency_ms", models.PositiveIntegerField()),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ("-created_at",)},
    )]
