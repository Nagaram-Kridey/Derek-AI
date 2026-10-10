from getpass import getpass
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

class Command(BaseCommand):
    help = "Create the single owner interactively; passwords never appear in command arguments."
    def add_arguments(self, parser):
        parser.add_argument("username")
    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(is_active=True).exists():
            raise CommandError("An active owner already exists. Use changepassword to reset its password.")
        password = getpass("Owner password: ")
        if password != getpass("Confirm password: "):
            raise CommandError("Passwords differ")
        user = User(username=options["username"])
        try:
            validate_password(password, user)
            if len(password) < 12:
                raise ValidationError("Use at least 12 characters")
        except ValidationError as exc:
            raise CommandError(str(exc)) from exc
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS("Owner created. Sign in through the dashboard."))
