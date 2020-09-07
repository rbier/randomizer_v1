from django.contrib.auth.models import User
from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone


class Table(models.Model):
    name = models.TextField(unique=True)
    is_hidden = models.BooleanField(default=False)
    arm_1 = models.TextField(blank=True, null=True)
    arm_2 = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    def slug(self):
        return slugify(self.name)


class Row(models.Model):
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    key = models.IntegerField()
    patient_id = models.IntegerField(blank=True, null=True)
    site_id = models.IntegerField(blank=True, null=True)
    randomization_arm = models.IntegerField()
    processed = models.BooleanField(default=False)
    reservation = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    processed_datetime = models.DateTimeField(blank=True, null=True)
    reservation_datetime = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'Table={self.table.name}, Patient ID={self.patient_id}, Site ID={self.site_id}'

    class Meta:
        indexes = [models.Index(fields=['key']), models.Index(fields=['table'])]
        ordering = ('patient_id', 'pk')

    def reserve(self, user, patient_id):
        self.reservation = user
        self.reservation_datetime = timezone.localtime()
        self.patient_id = patient_id
        self.save()

    def complete_reservation(self):
        self.processed = True
        self.processed_datetime = timezone.localtime()
        self.save()

    def cancel_reservation(self):
        self.reservation = None
        self.reservation_datetime = None
        self.patient_id = None
        self.save()


class BaseColumn(models.Model):
    name = models.TextField()
    number_of_options = models.IntegerField()
    potential_values = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    def potential_values_list(self):
        if not hasattr(self, '_potential_values_list'):
            if self.potential_values:
                self._potential_values_list = self.potential_values.split(',')
            else:
                self._potential_values_list = [x for x in range(self.number_of_options)]
        return self._potential_values_list

    def choices(self, include_blank=True):
        return ([('', ' ')] if include_blank else []) + \
               [(str(i), str(x)) for i, x in enumerate(self.potential_values_list())]

    class Meta:
        abstract = True


class Column(BaseColumn):
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    table_index = models.IntegerField()

    class Meta:
        ordering = ('table_index',)
        unique_together = (('table', 'table_index',), ('table', 'name',))


class SiteIdColumn(BaseColumn):
    table = models.OneToOneField(Table, related_name='site_id_column', on_delete=models.CASCADE)
