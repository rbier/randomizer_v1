import html
from . import models


def validate_input_text(value):
    if value is None:
        raise ValueError('Value cannot be blank.')
    value = str(value)
    if not value:
        raise ValueError('Value cannot be blank.')
    if html.escape(value) != value or ',' in value:
        raise ValueError('Please limit text to alphanumeric characters and spaces.')


def validate_table_name(name):
    try:
        validate_input_text(name)
    except ValueError as e:
        raise ValueError(f'Invalid table name. {e}')
    if models.Table.objects.filter(name=name).exists():
        raise KeyError('Table already exists with this name.')


def validate_column_names(column_names):
    if len(set(column_names)) != len(column_names):
        raise ValueError('Duplicate column name seen.')
    try:
        for column_name in column_names:
            validate_input_text(column_name)
    except ValueError as e:
        raise ValueError(f'Invalid column name. {e}')


def validate_potential_column_values(column_values):
    if len(set(column_values)) != len(column_values):
        raise ValueError('Duplicate column values seen.')
    try:
        for column_value in column_values:
            validate_input_text(column_value)
    except ValueError as e:
        raise ValueError(f'Invalid column value. {e}')
