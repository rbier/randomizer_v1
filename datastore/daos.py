from django.db.models import Max
from django.db.transaction import atomic
from django.urls import reverse
from django.utils.translation import gettext
from . import input_validators
from . import models
from . import row_transforms
from . import table_creation
from permissions import daos as permissions_daos


@atomic
def create_table(name, owner):
    if not owner:
        raise PermissionError('Owner must be provided for a table to be created')
    if not table_creation.user_can_create_tables(owner):
        raise PermissionError('Owner must have permissions to create a table')
    table = models.Table.objects.create(name=name)
    permissions_daos.set_table_owner(table, owner)
    return TableCreationDAO(table, owner)


def register_user_for_table(request, user, table_activation_code):
    permissions_daos.register_user_for_table(user, table_activation_code)
    from django.conf import settings
    if settings.SLACK_TOKEN:
        from slacker import Slacker
        approval_site = request.build_absolute_uri(reverse('access_approval'))
        slack = Slacker(settings.SLACK_TOKEN)
        slack_message = f'`{user}` has requested access to table `{activation_code.table.name}` ' \
                        f'with activation code `{table_activation_code}`. ' \
                        f'You may approve this request at {approval_site}.'
        slack.chat.post_message('#study-randomizer', slack_message)


class TableDAO:
    def __init__(self, table, user):
        self._table = table
        self._user = user
        self._activation_codes = None
        self._columns = None
        table_permissions_dao = permissions_daos.TablePermissionsDAO(table, user)
        self.is_owner = table_permissions_dao.is_owner()
        self.site_ids = table_permissions_dao.site_ids()
        if not self.site_ids:
            raise PermissionError(gettext('NoSiteIdError'))

    def column_names(self):
        return [column.name for column in self._get_columns()]

    def fields_to_row_key(self, fields):
        return row_transforms.fields_to_row_key(fields, self._get_columns())

    def get_row_values(self, row):
        return row_transforms.row_key_to_row_values(row.key, self._get_columns())

    def row_dao_iter(self, as_staff):
        rows = self._table.row_set.all()
        if as_staff or not self.is_owner:
            rows = rows.filter(reservation=self._user, processed=True).order_by('patient_id')
        for row in rows:
            yield RowDAO(row, self)

    def has_site_id_column(self):
        return hasattr(self._table, 'site_id_column')

    def site_id_column_name(self):
        return self._table.site_id_column.name

    def site_id_column_values(self):
        return self._table.site_id_column.potential_values_list()

    def get_arm_name(self, arm):
        if int(arm) == 1:
            return self._table.arm_1 or '1'
        if int(arm) == 2:
            return self._table.arm_2 or '2'
        raise ValueError(gettext('InvalidArmError'))

    def get_activation_code_data(self):
        if not self.is_owner:
            raise PermissionError('Only the table owner can access activation codes')
        if not self._activation_codes:
            activation_codes = self._table.activationcode_set.all()
            self._activation_codes = self._generate_activation_code_data(activation_codes)
        return self._activation_codes

    def _generate_activation_code_data(self, activation_codes):
        if self.has_site_id_column():
            potential_values = self._table.site_id_column.choices(include_blank=False)
            column_index_to_name = {int(i): x for i, x in potential_values}
            activation_codes = [(column_index_to_name[activation_code.site_id], activation_code.code)
                                for activation_code in activation_codes]
            return sorted(activation_codes)
        return [(activation_code.code,) for activation_code in activation_codes]

    def _get_columns(self):
        if not self._columns:
            self._columns = self._table.column_set.all()
        return self._columns


class TableCreationDAO(TableDAO):
    def __init__(self, table, user):
        super().__init__(table, user)
        if not self.is_owner:
            raise PermissionError('Only owner has permission to create table objects')

    def table_detail_args(self):
        return self._table.pk, self._table.slug()

    @atomic
    def create_column(self, name, value_options, is_site_id_column=False):
        if not name:
            raise ValueError('Name cannot be blank.')
        potential_values = ','.join([str(x) for x in value_options])
        kwargs = {'table': self._table, 'name': name,
                  'number_of_options': len(value_options), 'potential_values': potential_values}
        if is_site_id_column:
            self._table.site_id_column = models.SiteIdColumn.objects.create(**kwargs)
        else:
            table_index = self._table.column_set.count()
            models.Column.objects.create(table_index=table_index, **kwargs)

    @atomic
    def update_site_id_column(self, value_options):
        potential_values = ','.join([str(x) for x in value_options])
        column = self._table.site_id_column
        if not potential_values.startswith(column.potential_values + ','):
            raise ValueError('New site id column keys do not contain existing keys')
        column.number_of_options = len(value_options)
        column.potential_values = potential_values
        column.save()

    @atomic
    def create_row(self, fields, row_transformer):
        cleaned_fields = {}
        site_id_column_name = self._table.site_id_column.name if self.has_site_id_column() else None
        kwargs = {'table': self._table}
        for field_name, field_value in fields.items():
            if field_name == 'randomization_arm':
                kwargs['randomization_arm'] = int(field_value)
            elif field_name == 'processed':
                kwargs['processed'] = int(field_value)
            elif field_name == site_id_column_name:
                kwargs['site_id'] = row_transformer[field_name][field_value]
            else:
                cleaned_fields[field_name] = row_transformer[field_name][field_value]
        kwargs['key'] = self.fields_to_row_key(cleaned_fields)
        return models.Row.objects.create(**kwargs)

    def create_activation_codes(self):
        permissions_daos.create_activation_codes(self._table)

    @atomic
    def rename_columns_and_values(self, updates):
        self.rename_randomization_arms(updates)
        self._validate_potential_column_names(updates)
        for column_index, column in enumerate(self._get_columns()):
            self.rename_column_and_values(updates, column, column_index)
        if self.has_site_id_column():
            self.rename_column_and_values(updates, self._table.site_id_column, len(self._get_columns()))

    @atomic
    def rename_column_and_values(self, updates, column, column_index):
        column.name = updates.get(f'col_{column_index}')
        input_validators.validate_input_text(column.name)
        choices = []
        for choice_index in range(column.number_of_options):
            choice_name = updates.get(f'col_{column_index}_{choice_index}')
            choices.append(choice_name)
        input_validators.validate_potential_column_values(choices)
        column.potential_values = ','.join(choices)
        column.save()

    @atomic
    def rename_randomization_arms(self, updates):
        for arm in ['arm_1', 'arm_2']:
            input_validators.validate_input_text(updates[arm])
            setattr(self._table, arm, updates[arm])
        self._table.save()

    def validate_potential_column_values_against_existing(self, potential_column_values):
        column_name_to_column = {column.name: column for column in self._get_columns()}
        if len(potential_column_values) != len(column_name_to_column) + 1:
            raise KeyError('Invalid number of columns')
        for column_name in potential_column_values:
            column_to_compare = column_name_to_column.get(column_name)
            if column_to_compare:
                if set(column_to_compare.potential_values_list()) != set(potential_column_values[column_name]):
                    raise KeyError(f'Found mismatching column values for `{column_name}`.')
            elif self._table.site_id_column.name == column_name:
                for potential_column_value in potential_column_values[column_name]:
                    if potential_column_value in self._table.site_id_column.potential_values_list():
                        raise KeyError(f'Found pre-existing value for `{column_name}`.')
            else:
                raise KeyError(f'Column `{column_name}` not found.')

    def get_column_value_options(self):
        return {column.name: column.potential_values_list()
                for column in list(self._get_columns()) + [self._table.site_id_column]}

    def _validate_potential_column_names(self, updates):
        column_names = []
        for column_index in range(len(self._get_columns()) + (1 if self.has_site_id_column() else 0)):
            column_names.append(updates.get(f'col_{column_index}'))
        input_validators.validate_column_names(column_names)


class TableReservationDAO(TableDAO):
    def column_names_and_choices_iter(self, include_site_column=False):
        for column in self._get_columns():
            yield column.name, column.choices()
        if self.has_site_id_column():
            site_id_column = self._table.site_id_column
            choices = site_id_column.choices()
            if include_site_column or self.site_ids == [None]:
                if not self.is_owner:
                    raise PermissionError('Only owner has permission to include all site columns')
                yield site_id_column.name, choices
            elif len(self.site_ids) > 1:
                choices = [x for i, x in enumerate(choices) if i == 0 or (i - 1) in self.site_ids]
                yield site_id_column.name, choices

    def my_reserved_row_pk(self):
        return self._my_reserved_row().pk

    def has_reserved_row(self):
        return self._get_reserved_row() is not None

    def validate_my_reserved_row(self, row):
        if not row:
            raise LookupError(gettext('NoRowReservationFoundError'))
        if row.reservation != self._user:
            raise PermissionError(gettext('NoRowPermissionError'))

    def get_reserved_row_dao(self):
        return RowDAO(self._my_reserved_row(), self)

    @atomic
    def reserve_next_available_row(self, fields):
        row = self._get_next_available_row(fields)
        if not row:
            raise LookupError(gettext('NoRowsAvailableError'))
        patient_id = self._calculate_patient_id(row.site_id)
        row.reserve(self._user, patient_id)
        return row

    @atomic
    def complete_my_reservation(self, row_pk):
        row = self._get_row_for_processing(row_pk)
        row.complete_reservation()
        return row

    @atomic
    def cancel_my_reservation(self, row_pk):
        row = self._get_row_for_processing(row_pk)
        row.cancel_reservation()
        return row

    @atomic
    def complete_override_reservation(self, row_pk):
        row = self._get_row_for_processing_override(row_pk)
        row.complete_reservation()
        return row

    @atomic
    def cancel_override_reservation(self, row_pk):
        row = self._get_row_for_processing_override(row_pk)
        row.cancel_reservation()
        return row

    def _get_next_available_row(self, fields):
        if self.has_reserved_row():
            raise PermissionError(gettext('RowReservationAlreadyExistsError'))
        kwargs = {'reservation__isnull': True, 'processed': False}
        if self.has_site_id_column():
            kwargs['site_id'] = self._process_site_id_column(fields)
        kwargs['key'] = self.fields_to_row_key(fields)
        return self._table.row_set.filter(**kwargs).select_for_update().first()

    def _get_row_for_processing(self, row_pk):
        row = self._my_reserved_row(select_for_update=True)
        if int(row_pk) != row.pk:
            raise KeyError(gettext('RowReservationDoesNotMatchError'))
        return row

    def _my_reserved_row(self, select_for_update=False):
        row = self._get_reserved_row(select_for_update)
        self.validate_my_reserved_row(row)
        return row

    def _get_row_for_processing_override(self, row_pk):
        if not self.is_owner:
            raise PermissionError('Cannot override row processing as non-owner')
        kwargs = {'reservation__isnull': False, 'processed': False}
        return self._table.row_set.select_for_update().get(pk=row_pk, **kwargs)

    def _get_reserved_row(self, select_for_update=False):
        kwargs = {'reservation__isnull': False, 'processed': False}
        if None not in self.site_ids:
            kwargs['site_id__in'] = self.site_ids
        query = self._table.row_set.filter(**kwargs)
        if select_for_update:
            query = query.select_for_update()
        return query.first()

    def _process_site_id_column(self, fields):
        column_name = self._table.site_id_column.name
        if column_name in fields:
            if len(self.site_ids) == 1 and self.site_ids[0] is not None:
                raise KeyError(gettext('SiteIdPopulatedError'))
            if self.site_ids != [None] and fields[column_name] not in self.site_ids:
                raise KeyError(gettext('SiteIdInvalidError'))
            site_id = fields[column_name]
            del fields[column_name]
            return site_id
        if len(self.site_ids) == 1:
            return self.site_ids[0]
        raise KeyError(gettext('SiteIdMissingError'))

    def _calculate_patient_id(self, site_id):
        all_site_rows = self._table.row_set.select_for_update().filter(site_id=site_id)
        aggregation = all_site_rows.aggregate(Max('patient_id'))
        if aggregation.get('patient_id__max'):
            return aggregation['patient_id__max'] + 1
        number_of_base_digits = len(str(all_site_rows.count() + 100))
        return ((site_id or 0) + 1) * 10 ** number_of_base_digits + 1


class RowDAO:
    def __init__(self, row, table_dao):
        self._row = row
        self._table_dao = table_dao
        self.is_table_owner = table_dao.is_owner
        if not self.is_table_owner:
            try:
                table_dao.validate_my_reserved_row(row)
            except PermissionError:
                raise PermissionError(gettext('NoAccessError'))

    def get_values(self):
        return self._table_dao.get_row_values(self._row)

    def get_site(self):
        if self._table_dao.has_site_id_column():
            potential_values = self._table_dao.site_id_column_values()
            return potential_values[self._row.site_id]
        return None

    def get_patient_id(self):
        if not self._row.patient_id:
            return ''
        return str(self._row.patient_id)

    def get_reservation_username(self):
        if not self._row.reservation:
            return ''
        return self._row.reservation.username

    def get_randomization_arm(self):
        return self._table_dao.get_arm_name(self._row.randomization_arm)

    def is_locked_for_reservation(self):
        return self._row.reservation is not None and not self._row.processed

    def get_last_changed(self):
        last_changed = self._row.processed_datetime
        if self._row.reservation_datetime:
            if not last_changed or last_changed < self._row.reservation_datetime:
                last_changed = self._row.reservation_datetime
        if last_changed:
            return last_changed.strftime("%m/%d/%Y %H:%M:%S %Z")
        return ''

    def get_pk(self):
        return self._row.pk
