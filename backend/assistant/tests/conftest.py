import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

@pytest.fixture(autouse=True)
def configuration(settings):
    settings.SECURE_SSL_REDIRECT = False
    settings.CELERY_TASK_ALWAYS_EAGER = False

@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="owner", password="testing-a-long-password")

@pytest.fixture
def client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client
