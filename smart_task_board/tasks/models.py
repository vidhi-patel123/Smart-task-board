from django.db import models
from django.utils import timezone

class Priority(models.Model):
    name = models.CharField(max_length=25, unique=True)

    def __str__(self):
        return self.name

class Task(models.Model):
    # PRIORITY_CHOICES = [
    #     ('low', 'Low'),
    #     ('medium', 'Medium'),
    #     ('high', 'High'),
    # ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('locked', 'Locked'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]

    title = models.CharField(max_length=255)
    priority = models.ForeignKey(Priority, on_delete=models.CASCADE, related_name='tasks')
    estimated_time = models.PositiveIntegerField(help_text="Estimated time in minutes")
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    locked_until = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    is_odd_minute_task = models.BooleanField(default=False)
    completion_attempts = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} [{self.priority}] - {self.status}"

    def is_locked(self):
        if self.status == 'locked' and self.locked_until:
            if timezone.now() < self.locked_until:
                return True
            else:
                self.status = 'pending'
                self.save(update_fields=['status'])
        return False

    def is_expired(self):
        if self.is_odd_minute_task and self.deadline:
            if timezone.now() > self.deadline and self.status == 'pending':
                self.status = 'expired'
                self.save(update_fields=['status'])
                return True
        return False

    def seconds_until_unlock(self):
        if self.locked_until and timezone.now() < self.locked_until:
            return max(0, int((self.locked_until - timezone.now()).total_seconds()))
        return 0

    def seconds_until_deadline(self):
        if self.deadline and timezone.now() < self.deadline:
            return max(0, int((self.deadline - timezone.now()).total_seconds()))
        return 0
