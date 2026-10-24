from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("assistant", "0010_personal_memory")]
    operations = [migrations.AddField(model_name="assistantpreferences", name="response_detail",
        field=models.CharField(max_length=12, default="auto", choices=[(v, v) for v in ("auto", "brief", "balanced", "detailed")]))]
