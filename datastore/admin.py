from django.contrib import admin
from django.db.models import TextField
from django.forms import TextInput
from . import models


class ReservationIsNullFilter(admin.SimpleListFilter):
    title = 'reserved'
    parameter_name = 'reserved'

    def lookups(self, request, model_admin):
        return [(x, x) for x in [True, False]]

    def queryset(self, request, queryset):
        if self.value() == 'True':
            return queryset.filter(reservation__isnull=False)
        if self.value() == 'False':
            return queryset.filter(reservation__isnull=True)
        return queryset


class RowAdmin(admin.ModelAdmin):
    readonly_fields = ('id', 'table_name', 'site_id', 'randomization_arm', 'key')
    exclude = ('patient_id',)
    list_display = ('id', 'table_name', 'site_id', 'randomization_arm',
                    'processed', 'processed_datetime', 'reservation', 'reservation_datetime', 'key')
    list_editable = ('processed', 'reservation')
    list_filter = ('table', 'processed', ReservationIsNullFilter)
    list_prefetch_related = ('table', 'table__column_set')
    search_fields = ('patient_id',)

    @staticmethod
    def table_name(row):
        return row.table.name


class ColumnAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'table', 'table_index')
    list_filter = ('table',)
    readonly_fields = ('table_index', 'number_of_options')
    formfield_overrides = {
        TextField: {'widget': TextInput},
    }


class SiteIdColumnAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'table')
    list_filter = ('table',)
    readonly_fields = ('number_of_options',)
    formfield_overrides = {
        TextField: {'widget': TextInput},
    }


class TableAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'site_id_column', 'arm_1', 'arm_2', 'is_hidden')
    list_editable = ('is_hidden',)
    list_filter = ('is_hidden',)


admin.site.register(models.Row, RowAdmin)
admin.site.register(models.Column, ColumnAdmin)
admin.site.register(models.SiteIdColumn, SiteIdColumnAdmin)
admin.site.register(models.Table, TableAdmin)
