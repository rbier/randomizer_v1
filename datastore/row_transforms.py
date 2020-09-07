from django.utils.translation import gettext

# Tables do not have a fixed column count, so rows are stored as a hash.
# Each column is assumed to have a fixed number of options, and these options
# are stored in a zero-indexed count (e.g. four options = [0, 1, 2, 3]).
# The hash is calculated as:
#   First column's number plus
#   Second column's number multiplied by the number of options available for
#   the first number, plus
#   Third column's number multiplied by the number of options available for
#   the first and the second number
#   Etc as necessary.

# So if there are five columns with option counts of [2, 3, 4, 5, 6]
# and the column values are [1, 2, 3, 4, 5], then the hash will be
# 1 + 2 * 2 + 3 * 3 * 2 + 4 * 4 * 3 * 2 + 5 * 5 * 4 * 3 * 2


def validate_row_values(row_values, columns):
    if len(row_values) != len(columns):
        raise IndexError(gettext('RowLengthError'))


def validate_row_value(row_value, column):
    if row_value < 0:
        raise IndexError(gettext('RowValueError'))
    if row_value >= column.number_of_options:
        raise IndexError(gettext('RowValueError'))


def validate_fields(fields, columns):
    if fields.keys() != set(column.name for column in columns):
        raise KeyError(gettext('RowKeysError'))


def row_values_to_row_key(row_values, columns):
    validate_row_values(row_values, columns)
    row_key = 0
    for row_value, column in reversed(list(zip(row_values, columns))):
        validate_row_value(row_value, column)
        row_key = row_key * column.number_of_options + row_value
    return row_key


def row_key_to_row_values(row_key, columns):
    row_values = []
    for column in columns:
        column_value = int(row_key % column.number_of_options)
        transformer = column.potential_values_list()
        row_values.append(transformer[column_value])
        row_key = (row_key - column_value) / column.number_of_options
    return row_values


def fields_to_row_key(fields, columns):
    validate_fields(fields, columns)
    row_values = [fields[column.name] for column in columns]
    return row_values_to_row_key(row_values, columns)
