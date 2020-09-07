from django.test import TestCase
from . import models
from . import row_transforms


class RowTestCase(TestCase):
    def setUp(self):
        self.table = models.Table.objects.create(name='test')
        for i in range(3):
            models.Column.objects.create(name=f'col{i + 1}', table_index=i, table=self.table, number_of_options=i + 2)

    def test_row_key_transform(self):
        self.row_key_transform({'col1': 1, 'col2': 2, 'col3': 3}, 1 + 4 + 18)
        self.row_key_transform({'col1': 0, 'col2': 0, 'col3': 3}, 0 + 0 + 18)
        self.row_key_transform({'col1': 0, 'col2': 0, 'col3': 0}, 0 + 0 + 0)

    def test_row_key_transform_exceptions(self):
        with self.assertRaises(IndexError):
            self.row_key_transform({'col1': 1, 'col2': 2, 'col3': 4}, None)
        with self.assertRaises(IndexError):
            self.row_key_transform({'col1': 2, 'col2': 0, 'col3': 0}, None)
        with self.assertRaises(IndexError):
            self.row_key_transform({'col1': 0, 'col2': -1, 'col3': 0}, None)
        with self.assertRaises(KeyError):
            self.row_key_transform({'col1': 0, 'col3': 0}, None)
        with self.assertRaises(KeyError):
            self.row_key_transform({'col1': 0, 'col2': 0, 'col3': 0, 'col4': 0}, None)

    def row_key_transform(self, input_fields, expected_row_key):
        columns = self.table.column_set.all()
        row_key = row_transforms.fields_to_row_key(input_fields, columns)
        self.assertEqual(row_key, expected_row_key)
        input_values = [input_fields[field_name] for field_name in sorted(input_fields.keys())]
        row_key = row_transforms.row_values_to_row_key(input_values, columns)
        self.assertEqual(row_key, expected_row_key)
        row_values = row_transforms.row_key_to_row_values(row_key, columns)
        self.assertEqual(row_values, input_values)

