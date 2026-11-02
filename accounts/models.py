from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Quản trị viên'),
        ('MANAGER', 'Quản lý/Thủ kho'),
        ('STAFF', 'Nhân viên (Lễ tân/KTV)'),
    ]
    full_name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='STAFF')

    class Meta:
        db_table = 'users'
