# models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
            ('admin', 'Admin'),
            ('controller', 'Controller'),
            ('manager', 'Manager'),
        )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='manager')
    user_id = models.CharField(max_length=50, unique=True)  # Custom user_id field
    username = models.CharField(max_length=150, unique=False)
    USERNAME_FIELD = "user_id"
    REQUIRED_FIELDS = ["username", "email"]

    def __str__(self):
            return self.username
        
class Tag(models.Model):
    tag_name = models.CharField(max_length=100)
    tag_value = models.IntegerField()
    tag_id = models.CharField(max_length=50, unique=True)
    department = models.CharField(max_length=100)
    status = models.BooleanField(default=False)  # New status field: True=On, False=Off
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def __str__(self):
        return self.tag_name

class TagHistory(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    status = models.BooleanField()  # True=On, False=Off
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.tag.tag_name} - {'On' if self.status else 'Off'} at {self.timestamp}"
    
class ScheduleGroup(models.Model):
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    tags = models.ManyToManyField(Tag)
    days = models.JSONField()  # Store days as JSON, e.g., {"sun": true, "mon": false, ...}
    on_time = models.TimeField()
    off_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class ScheduleHistory(models.Model):
    schedule_group = models.ForeignKey(ScheduleGroup, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    status = models.BooleanField()  # True=On, False=Off
    executed_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"{self.schedule_group.name} - {self.tag.tag_name} - {'ON' if self.status else 'OFF'}"
    
class PLCConnection(models.Model):
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField()

    def __str__(self):
        return f"({self.ip_address}:{self.port})"

    class Meta:
        # Ensure only one PLCConnection exists
        constraints = [
            models.UniqueConstraint(fields=['id'], name='unique_plc_connection')
        ]
