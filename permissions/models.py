from django.contrib.auth.models import User
from django.core.validators import ValidationError
from django.db import models
from random import randint
from datastore.models import Table


class TablePermission(models.Model):
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_owner = models.BooleanField(default=False)


    class Meta:
        unique_together = (('table', 'user'),)

    def __str__(self):
        return f'Table={self.table.name}, User={self.user}, IsOwner={self.is_owner}'


class TableSiteIdAccess(models.Model):
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    site_id = models.IntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=False)


class ActivationCode(models.Model):
    def __str__(self):
        if not self.table:
            return super().__str__
        return f'ActivationCode for `{self.table.name}` ({self.code})'

    @staticmethod
    def activation_code_validator(code):
        if len(code) != 8:
            raise ValidationError('Code must be 8 characters long')

    @staticmethod
    def generate_code():
        potential_letters = 'BCDFGHJKLMNPQRSTVWXZ'
        code = None
        while not code:
            code = ''.join(potential_letters[randint(0, len(potential_letters) - 1)] for _ in range(8))
            if ActivationCode.objects.filter(code=code).exists():
                code = None
        return code

    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    code = models.CharField(max_length=16, unique=True, validators=[activation_code_validator.__func__],
                            default=generate_code.__func__)
    site_id = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = (('table', 'site_id',),)
