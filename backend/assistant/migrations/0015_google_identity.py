from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def preserve_owner(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    active = User.objects.filter(is_active=True)
    if active.count() == 1:
        owner = active.first()
        if owner.password and not owner.password.startswith("!"):
            User.objects.filter(pk=owner.pk).update(is_staff=True)


class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL),
                    ("assistant", "0014_whatsappsettings_whatsappwatch_whatsappobservation_and_more")]
    operations = [
        migrations.CreateModel(name="GoogleIdentity", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("subject", models.CharField(max_length=255, unique=True)),
            ("email", models.EmailField(max_length=254)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="google_identity", to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="GoogleLoginChallenge", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("digest", models.CharField(max_length=64, unique=True)),
            ("nonce_digest", models.CharField(max_length=64)),
            ("binding_digest", models.CharField(max_length=64)),
            ("expires_at", models.DateTimeField()),
            ("consumed", models.BooleanField(default=False)),
        ]),
        migrations.RunPython(preserve_owner, migrations.RunPython.noop),
    ]
