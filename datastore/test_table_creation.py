from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.test import TestCase
from . import daos
from . import models
from . import table_creation


class TableImportValidationTestCase(TestCase):
    def test_cell_data_validation(self):
        table_creation.validate_cell_data('randomization_arm', '1')
        table_creation.validate_cell_data('randomization_arm', '2')
        with self.assertRaises(ValueError):
            table_creation.validate_cell_data('randomization_arm', '0')
        with self.assertRaises(ValueError):
            table_creation.validate_cell_data('randomization_arm', '01')
        with self.assertRaises(ValueError):
            table_creation.validate_cell_data('randomization_arm', '10')
        with self.assertRaises(ValueError):
            table_creation.validate_cell_data('randomization_arm', '-1')
        with self.assertRaises(ValueError):
            table_creation.validate_cell_data('randomization_arm', '3')
        with self.assertRaises(ValueError):
            table_creation.validate_cell_data('randomization_arm', 'hello')
        with self.assertRaises(ValueError):
            table_creation.validate_cell_data('randomization_arm', ' 1')
        table_creation.validate_cell_data('processed', '0')
        table_creation.validate_cell_data('processed', '1')
        with self.assertRaises(ValueError):
            table_creation.validate_cell_data('processed', '01')
        with self.assertRaises(ValueError):
            table_creation.validate_cell_data('processed', '10')
        with self.assertRaises(ValueError):
            table_creation.validate_cell_data('processed', '-1')
        with self.assertRaises(ValueError):
            table_creation.validate_cell_data('processed', '2')
        with self.assertRaises(ValueError):
            table_creation.validate_cell_data('processed', 'hello')
        with self.assertRaises(ValueError):
            table_creation.validate_cell_data('processed', ' 1')
        table_creation.validate_cell_data('column_name', '0')
        table_creation.validate_cell_data('column_name', '1')
        table_creation.validate_cell_data('column_name', '2')
        table_creation.validate_cell_data('column_name', '1000')
        table_creation.validate_cell_data('column_name', 'hello')
        table_creation.validate_cell_data('column_name', ' 1')

    def test_row_data_validation(self):
        table_creation.validate_row_data_core({'randomization_arm': '1', 'processed': '1', 'column_name': '1'})
        table_creation.validate_row_data_core({'randomization_arm': '2', 'column_name': '2'})
        table_creation.validate_row_data_core({'randomization_arm': '2', 'processed': '0', 'column_name': '1000'})
        table_creation.validate_row_data_core({'randomization_arm': '1', 'column_name': '0'})
        table_creation.validate_row_data_core({'randomization_arm': '1', 'column_name': '-1'})
        table_creation.validate_row_data_core({'randomization_arm': '1', 'column_name': 'hello'})
        with self.assertRaises(ValueError):
            table_creation.validate_row_data_core({'randomization_arm': '-1', 'processed': '0', 'column_name': '0'})
        with self.assertRaises(ValueError):
            table_creation.validate_row_data_core({'randomization_arm': '1', 'processed': '-1', 'column_name': '0'})
        with self.assertRaises(KeyError):
            table_creation.validate_row_data_core({'column_name': '-1'})

    def test_column_data_validation(self):
        table_creation.validate_potential_column_values({'key': [0, 1, 2, 3]})
        table_creation.validate_potential_column_values({'key': [3, 2, 1, 0]})
        table_creation.validate_potential_column_values({'key': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
        table_creation.validate_potential_column_values({'key': ['1', '2']})
        table_creation.validate_potential_column_values({'key': ['0', '2']})
        with self.assertRaises(ValueError):
            table_creation.validate_potential_column_values({'key': ['0']})
        with self.assertRaises(ValueError):
            table_creation.validate_potential_column_values({'key': []})
        with self.assertRaises(ValueError):
            table_creation.validate_potential_column_values({'key': ['0', '0']})


class TableImportTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='test', is_staff=True)

    def test_table_creation_and_destruction(self):
        header = ['randomization_arm', 'processed', 'column_name']
        rows = [{'randomization_arm': '1', 'processed': '1', 'column_name': '0'},
                {'randomization_arm': '1', 'processed': '1', 'column_name': '3'},
                {'randomization_arm': '2', 'processed': '1', 'column_name': '3'}]
        table_creation.validate_table_data_core(header, rows, None)
        table_creation.GenericTableCreator(header, rows, 'test1', None, self.user).create_table()
        self.assertEqual(len(models.Table.objects.filter(name='test1')), 1)
        columns = models.Column.objects.filter(table__name='test1')
        self.assertEqual(len(columns), 1)
        column = columns[0]
        self.assertEqual(column.table_index, 0)
        self.assertEqual(column.name, 'column_name')
        self.assertEqual(column.number_of_options, 2)
        self.assertEqual(column.potential_values, '0,3')
        rows = models.Row.objects.filter(table__name='test1')
        self.assertEqual(sum(row.key for row in rows), 0 + 1 + 1)
        self.assertEqual(sum(row.processed for row in rows), 1 + 1 + 1)
        self.assertEqual(sum(row.randomization_arm for row in rows), 1 + 1 + 2)
        models.Table.objects.filter(name='test1').delete()
        self.assertEqual(len(models.Table.objects.filter(name='test1')), 0)
        self.assertEqual(len(models.Column.objects.filter(table__name='test1')), 0)
        self.assertEqual(len(models.Row.objects.filter(table__name='test1')), 0)

    def test_table_site_id(self):
        header = ['randomization_arm', 'processed', 'column_name', 'center_id']
        rows = [{'randomization_arm': '1', 'processed': '1', 'column_name': y, 'center_id': x}
                for x in range(1, 11) for y in range(10)]
        table_creation.validate_table_data_core(header, rows, None)
        with self.assertRaises(KeyError):
            table_creation.validate_table_data_core(header, rows, 'invalid_row')
        table_creation.validate_table_data_core(header, rows, 'center_id')
        table_creator = table_creation.GenericTableCreator(header, rows, 'test_site_id', 'center_id', self.user)
        table_creator.create_table()
        rows.append({'randomization_arm': '1', 'processed': '1', 'column_name': 1000000, 'center_id': 1})
        table_creator = table_creation.GenericTableCreator(header, rows, 'test_site_id_2', 'center_id', self.user)
        table_creator.create_table()

    def test_table_creation_no_processing(self):
        header = ['randomization_arm', 'column_name']
        rows = [{'randomization_arm': '1', 'column_name': '0'},
                {'randomization_arm': '1', 'column_name': '1'},
                {'randomization_arm': '2', 'column_name': '1'}]
        table_creation.validate_table_data_core(header, rows, None)
        table_creation.GenericTableCreator(header, rows, 'test2', None, self.user).create_table()
        self.assertEqual(len(models.Table.objects.filter(name='test2')), 1)
        columns = models.Column.objects.filter(table__name='test2')
        self.assertEqual(len(columns), 1)
        column = columns[0]
        self.assertEqual(column.table_index, 0)
        self.assertEqual(column.name, 'column_name')
        self.assertEqual(column.number_of_options, 2)
        self.assertEquals(column.potential_values, '0,1')
        rows = models.Row.objects.filter(table__name='test2')
        self.assertEqual(sum(row.key for row in rows), 0 + 1 + 1)
        self.assertEqual(sum(row.processed for row in rows), 0 + 0 + 0)
        self.assertEqual(sum(row.randomization_arm for row in rows), 1 + 1 + 2)

    def test_table_creation_bad_table_column(self):
        header = ['randomization_arm', 'column_name', 'column_name']
        rows = [{'randomization_arm': '1', 'column_name': '0'},
                {'randomization_arm': '1', 'column_name': '1'},
                {'randomization_arm': '2', 'column_name': '1'}]
        with self.assertRaises(ValueError):
            table_creation.GenericTableCreator(header, rows, 'test3', None, self.user).create_table()
        self.assertEqual(len(models.Table.objects.filter(name='test3')), 0)

    def test_table_creation_bad_table_name(self):
        header = ['randomization_arm', 'column_name']
        rows = [{'randomization_arm': '1', 'column_name': '0'},
                {'randomization_arm': '1', 'column_name': '1'},
                {'randomization_arm': '2', 'column_name': '1'}]
        table_creation.GenericTableCreator(header, rows, 'test4', None, self.user).create_table()
        with self.assertRaises(IntegrityError):
            table_creation.GenericTableCreator(header, rows, 'test4', None, self.user).create_table()


class TableAppendImportTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='test', is_staff=True)
        header = ['randomization_arm', 'processed', 'column_name', 'site_id']
        rows = [{'randomization_arm': '1', 'processed': '1', 'column_name': '0', 'site_id': 'a'},
                {'randomization_arm': '1', 'processed': '1', 'column_name': '3', 'site_id': 'b'},
                {'randomization_arm': '2', 'processed': '1', 'column_name': '3', 'site_id': 'b'}]
        table_creator = table_creation.GenericTableCreator(header, rows, 'test_append', 'site_id', self.user)
        table_creation_dao = table_creator.create_table()
        self.table = table_creation_dao._table

    def test_table_creation_and_append(self):
        table_append_dao = daos.TableCreationDAO(self.table, self.user)
        header = ['randomization_arm', 'column_name']
        rows = []
        with self.assertRaises(KeyError):
            table_creation.GenericTableAppender(header, rows, table_append_dao).append_to_table()
        header = ['randomization_arm', 'column_name', 'site_id', 'new_column']
        with self.assertRaises(KeyError):
            table_creation.GenericTableAppender(header, rows, table_append_dao).append_to_table()
        header = ['randomization_arm', 'site_id', 'column_name']
        rows = [{'randomization_arm': '1', 'column_name': '0', 'site_id': 'a'},
                {'randomization_arm': '1', 'column_name': '3', 'site_id': 'b'},
                {'randomization_arm': '2', 'column_name': '3', 'site_id': 'b'}]
        with self.assertRaises(KeyError):
            table_creation.GenericTableAppender(header, rows, table_append_dao).append_to_table()
        rows = [{'randomization_arm': '1', 'column_name': '0', 'site_id': 'c'},
                {'randomization_arm': '1', 'column_name': '3', 'site_id': 'd'},
                {'randomization_arm': '2', 'column_name': '3', 'site_id': 'd'}]
        table_creation.GenericTableAppender(header, rows, table_append_dao).append_to_table()
        self.assertEqual(len(models.Column.objects.filter(table__name='test_append')), 1)
        self.assertEqual(len(models.Row.objects.filter(table__name='test_append')), 6)
        self.assertEqual(table_append_dao.site_id_column_values(), ['a', 'b', 'c', 'd'])
        self.assertEqual(table_append_dao._table.site_id_column.number_of_options, 4)
        self.assertEqual(table_append_dao._table.site_id_column.potential_values, 'a,b,c,d')
