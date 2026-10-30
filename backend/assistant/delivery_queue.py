"""Select eligible chat bubbles without starving unrelated commands."""
from django.db.models import Exists, OuterRef
from django.utils import timezone
from .models import Delivery


def next_delivery():
    earlier_waiting=Delivery.objects.filter(
        command_id=OuterRef('command_id'),position__lt=OuterRef('position'),
        status__in=['pending','sending'])
    destination_busy=Delivery.objects.filter(destination=OuterRef('destination'),status='sending')
    return (Delivery.objects.filter(status='pending',due_at__lte=timezone.now())
            .annotate(waiting_for_prior=Exists(earlier_waiting),busy=Exists(destination_busy))
            .filter(waiting_for_prior=False,busy=False)
            .order_by('due_at','position').first())
