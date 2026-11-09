# -*- coding: utf-8 -*-
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0003_alter_item_conversion_rate_alter_item_import_price_and_more")]
    operations = [
        migrations.RunSQL("DROP TABLE IF EXISTS kho_thekho", reverse_sql=migrations.RunSQL.noop),
        migrations.CreateModel(
            name="TheKho",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ngay", models.DateTimeField(default=django.utils.timezone.now)),
                ("loai_bien_dong", models.CharField(default="Nhập mua NCC", max_length=50)),
                ("so_luong", models.DecimalField(decimal_places=3, max_digits=14)),
                ("ton_cuoi", models.DecimalField(decimal_places=3, max_digits=14)),
                ("chung_tu", models.CharField(max_length=50)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="the_kho", to="inventory.item")),
            ],
        ),
    ]
