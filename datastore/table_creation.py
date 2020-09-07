import csv
from collections import defaultdict, Counter
from django.db.transaction import atomic
from . import daos
from . import input_validators


def user_can_create_tables(user):
    return user.is_staff


def validate_cell_data(cell_name, cell_value):
    input_validators.validate_input_text(cell_value)
    if cell_name == 'processed':
        if cell_value not in ('0', '1'):
            raise ValueError(f'Expected 0 or 1 for `{cell_name}`, got {cell_value}.')
        return
    if cell_name == 'randomization_arm':
        if cell_value not in ('1', '2'):
            raise ValueError(f'Expected 1 or 2 for `{cell_name}`, got {cell_value}.')
        return


def validate_row_data_core(row):
    if 'randomization_arm' not in row:
        raise KeyError(f'Column `randomization_arm` is missing.')
    for key in row:
        validate_cell_data(key, row[key])


def validate_row_data(row, row_index, header, site_id_field=None, site_id_counter=None):
    try:
        validate_row_data_core(row)
        if set(header) != set(row.keys()):
            raise ValueError(f'Row keys do not match header.')
        if site_id_field:
            site_id_counter[row[site_id_field]] += 1
    except ValueError as e:
        raise ValueError(f'{e}. Line {row_index + 2}.')


def validate_table_data_core(header, rows, site_id_field):
    site_id_counter = Counter() if site_id_field else None
    if site_id_field and site_id_field not in header:
        raise KeyError(f'Site id field `{site_id_field}` not found in header')
    row_index = -1
    for row_index, row in enumerate(rows):
        validate_row_data(row, row_index, header, site_id_field, site_id_counter)
    if row_index == -1:
        raise ValueError('No data.')
    if site_id_counter and min(site_id_counter.values()) != max(site_id_counter.values()):
        raise KeyError('All sites must have the same number of rows')


def validate_table_data(csv_file, site_id_field):
    csv_reader = csv.DictReader(decode_utf8(csv_file))
    validate_table_data_core(csv_reader.fieldnames, csv_reader, site_id_field)


def validate_potential_column_values(potential_column_values):
    for column in potential_column_values:
        potential_values = sorted(set(potential_column_values[column]))
        if len(potential_values) <= 1:
            raise ValueError(f'For column `{column}`, did not see multiple values')
        input_validators.validate_potential_column_values(potential_values)


def decode_utf8(input_iterator):
    for l in input_iterator:
        yield l.decode('utf-8')


class BaseRowCreator:
    def __init__(self, table_creation_dao=None, site_id_field=None):
        self.table_creation_dao = table_creation_dao
        self.site_id_field = site_id_field
        if not self.site_id_field and table_creation_dao and table_creation_dao.has_site_id_column():
            self.site_id_field = table_creation_dao.site_id_column_name()
        self.row_transformer = defaultdict(dict)
        self.column_value_options = None

    def create_rows(self):
        for fields in self.rows():
            self.table_creation_dao.create_row(fields, self.row_transformer)

    def init_row_transformer(self):
        for key in self.column_value_options:
            for index, option in enumerate(self.column_value_options[key]):
                self.row_transformer[key][option] = index

    def create_activation_codes(self):
        self.table_creation_dao.create_activation_codes()

    def rows(self):
        raise NotImplementedError


class BaseTableCreator(BaseRowCreator):
    def __init__(self, table_name, site_id_field, owner):
        super().__init__(site_id_field=site_id_field)
        self.table_name = table_name
        self.owner = owner

    def calculate_column_value_options_and_row_count(self):
        potential_column_values = defaultdict(set)
        for row_index, row in enumerate(self.rows()):
            for key in row:
                if key not in ('randomization_arm', 'processed'):
                    potential_column_values[key].add(row[key])
        input_validators.validate_potential_column_values(potential_column_values)
        self.column_value_options = {key: sorted(potential_column_values[key]) for key in potential_column_values}

    def create_columns(self):
        column_names = self.column_names()
        input_validators.validate_column_names(column_names)
        header = [column_name for column_name in column_names
                  if column_name not in ('randomization_arm', 'processed')]
        for column_name in header:
            value_options = self.column_value_options[column_name]
            is_site_id_column = column_name == self.site_id_field
            self.table_creation_dao.create_column(column_name, value_options, is_site_id_column)

    @atomic
    def create_table(self):
        if not self.column_value_options:
            self.calculate_column_value_options_and_row_count()
        self.table_creation_dao = daos.create_table(self.table_name, self.owner)
        self.create_columns()
        self.init_row_transformer()
        self.create_rows()
        self.create_activation_codes()
        return self.table_creation_dao

    def rows(self):
        raise NotImplementedError

    def column_names(self):
        raise NotImplementedError


class CSVTableCreator(BaseTableCreator):
    def __init__(self, csv_file, table_name, site_id_field, owner):
        self.csv_file = csv_file
        self._columns = None
        super().__init__(table_name, site_id_field, owner)

    def rows(self):
        return csv.DictReader(decode_utf8(self.csv_file))

    def column_names(self):
        if not self._columns:
            self._columns = csv.DictReader(decode_utf8(self.csv_file)).fieldnames
        return self._columns


class GenericTableCreator(BaseTableCreator):
    def __init__(self, columns, rows, table_name, site_id_field, owner):
        self._rows = rows
        self._columns = columns
        super().__init__(table_name, site_id_field, owner)

    def rows(self):
        return self._rows

    def column_names(self):
        return self._columns


class BaseTableAppender(BaseRowCreator):
    def __init__(self, table_creation_dao):
        super().__init__(table_creation_dao)
        if not table_creation_dao.has_site_id_column():
            raise KeyError('Cannot append to a table without a site id column')
        self.column_value_options = None

    def calculate_column_value_options(self):
        potential_column_values = defaultdict(set)
        for row_index, row in enumerate(self.rows()):
            for key in row:
                if key not in ('randomization_arm', 'processed'):
                    potential_column_values[key].add(row[key])
        input_validators.validate_potential_column_values(potential_column_values)
        self.table_creation_dao.validate_potential_column_values_against_existing(potential_column_values)
        self.column_value_options = self.table_creation_dao.get_column_value_options()
        self.column_value_options[self.site_id_field] += \
            sorted(potential_column_values[self.site_id_field])

    def update_site_id_column(self):
        self.table_creation_dao.update_site_id_column(self.column_value_options[self.site_id_field])

    @atomic
    def append_to_table(self):
        if not self.column_value_options:
            self.calculate_column_value_options()
        self.update_site_id_column()
        self.init_row_transformer()
        self.create_rows()
        self.create_activation_codes()
        return self.table_creation_dao

    def rows(self):
        raise NotImplementedError

    def column_names(self):
        raise NotImplementedError


class CSVTableAppender(BaseTableAppender):
    def __init__(self, csv_file, table_creation_dao):
        self.csv_file = csv_file
        self._columns = None
        super().__init__(table_creation_dao)

    def rows(self):
        return csv.DictReader(decode_utf8(self.csv_file))

    def column_names(self):
        if not self._columns:
            self._columns = csv.DictReader(decode_utf8(self.csv_file)).fieldnames
        return self._columns


class GenericTableAppender(BaseTableAppender):
    def __init__(self, columns, rows, table_creation_dao):
        self._rows = rows
        self._columns = columns
        super().__init__(table_creation_dao)

    def rows(self):
        return self._rows

    def column_names(self):
        return self._columns
