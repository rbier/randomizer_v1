from django.db.transaction import atomic
from . import models


@atomic
def set_table_owner(table, owner):
    models.TablePermission.objects.get_or_create(table=table, user=owner, is_owner=True)
    models.TableSiteIdAccess.objects.get_or_create(table=table, user=owner, site_id=None, is_active=True)


@atomic
def register_user_for_table(user, table_activation_code):
    activation_code = models.ActivationCode.objects.get(code=table_activation_code)
    models.TablePermission.objects.get_or_create(user=user, table=activation_code.table)
    models.TableSiteIdAccess.objects.get_or_create(user=user, table=activation_code.table,
                                                   site_id=activation_code.site_id)

@atomic
def create_activation_codes(table):
    has_site_id_column = hasattr(table, 'site_id_column')
    site_ids = range(table.site_id_column.number_of_options) if has_site_id_column else [None]
    for site_id in site_ids:
        models.ActivationCode.objects.get_or_create(table=table, site_id=site_id)


def get_site(table_site_id_access):
    if table_site_id_access.site_id is None:
        return ''
    choices = table_site_id_access.table.site_id_column.potential_values_list()
    return choices[table_site_id_access.site_id]


def user_has_table_access(user, table):
    site_id_access = models.TableSiteIdAccess.objects.filter(table=table, user=user, is_active=True)
    return site_id_access.count() > 0


class TablePermissionsDAO:
    def __init__(self, table, user):
        self._table_permission = models.TablePermission.objects.get(table=table, user=user)
        self._table_site_id_access_queryset = models.TableSiteIdAccess.objects.filter(table=table, user=user,
                                                                                      is_active=True)

    def is_owner(self):
        return self._table_permission.is_owner

    def site_ids(self):
        return [table_site_id_access.site_id for table_site_id_access in self._table_site_id_access_queryset]


class TableSiteAccessDAO:
    def __init__(self, user):

        if not user.is_staff:
            raise PermissionError('Only staff members can manage table site access')
        self.user = user

    def get_inactive_queryset(self):
        table_site_id_access_queryset = self._get_accessible_table_site_id_access_queryset()
        return table_site_id_access_queryset.filter(is_active=False)

    @atomic
    def approve(self, table_site_id_access_pk):
        table_site_id_access_queryset = self._get_accessible_table_site_id_access_queryset()
        table_site_id_access = table_site_id_access_queryset.filter(pk=table_site_id_access_pk).first()
        if not table_site_id_access:
            raise PermissionError('Unable to grant access to table')
        user = table_site_id_access.user
        table_site_id_access.is_active = True
        table_site_id_access.save()
        user.is_active = True
        user.save()
        return user, table_site_id_access.table.name

    def _get_accessible_table_site_id_access_queryset(self):
        valid_table_permissions = models.TablePermission.objects.filter(user=self.user, is_owner=True)
        valid_table_ids = valid_table_permissions.values_list('table_id', flat=True)
        return models.TableSiteIdAccess.objects.filter(table_id__in=valid_table_ids)
