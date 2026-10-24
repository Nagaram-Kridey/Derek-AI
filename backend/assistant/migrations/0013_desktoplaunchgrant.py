from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('assistant','0012_roadmapboard'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name='DesktopLaunchGrant',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('digest',models.CharField(max_length=64,unique=True)),
        ('token_digest',models.CharField(max_length=64)),
        ('expires_at',models.DateTimeField()),
        ('consumed',models.BooleanField(default=False)),
        ('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,to=settings.AUTH_USER_MODEL)),
    ])]
