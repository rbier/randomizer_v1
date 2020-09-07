from django.contrib import admin
from . import models


class TablePermissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'table', 'user', 'is_owner')
    list_filter = ('table', 'user')


class TableSiteIdAccessAdmin(admin.ModelAdmin):
    list_display = ('id', 'table', 'user', 'site', 'is_active')
    list_filter = ('table', 'user', 'is_active')
    list_editable = ('is_active',)

    @staticmethod
    def site(obj):
        if obj.site_id is None:
            return '-'
        options = obj.table.site_id_column.potential_values_list()
        return options[obj.site_id]

class ActivationCodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'table', 'code', 'site_id')
    list_filter = ('table',)


admin.site.register(models.TablePermission, TablePermissionAdmin)
admin.site.register(models.TableSiteIdAccess, TableSiteIdAccessAdmin)
admin.site.register(models.ActivationCode, ActivationCodeAdmin)