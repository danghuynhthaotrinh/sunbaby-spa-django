from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin (Quản trị viên)'),
        ('QUAN_LY', 'Quản lý (QUAN_LY)'),
        ('THU_KHO', 'Thủ kho (THU_KHO)'),
        ('LE_TAN', 'Lễ tân (LE_TAN)'),
        ('KTV', 'Kỹ thuật viên (KTV)'),
    ]

    full_name = models.CharField(max_length=150, blank=True, verbose_name="Họ và tên")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='KTV', verbose_name="Vai trò")
    lock_reason = models.TextField(blank=True, null=True, verbose_name="Lý do khóa")

    def __str__(self):
        return f"{self.username} - {self.get_role_display()}"
