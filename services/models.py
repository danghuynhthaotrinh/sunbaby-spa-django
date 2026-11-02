from django.db import models

class Service(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    duration = models.IntegerField()
    price = models.DecimalField(max_digits=18, decimal_places=2)
    cost = models.DecimalField(max_digits=18, decimal_places=2, default=0.0)

    class Meta:
        db_table = 'services'

class ServiceBOM(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='boms')
    item = models.ForeignKey('inventory.Item', on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'service_bom'
        unique_together = ('service', 'item')
