from django.contrib.auth.models import User
from django.db.transaction import atomic
from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from . import daos
from . import input_validators
from . import models
from permissions import models as permissions_models


class TableCreationTestCase(TestCase):
    def setUp(self):
        models.Table.objects.create(name='old_table')
        self.user = User.objects.create(username='test_not_staff')
        self.staff = User.objects.create(username='test_staff', is_staff=True)
        self.table_creation_dao = daos.create_table('dao_test', self.staff)

    def test_table_name_validity(self):
        input_validators.validate_table_name('new_table')
        with self.assertRaises(KeyError):
            input_validators.validate_table_name('old_table')
        with self.assertRaises(ValueError):
            input_validators.validate_table_name('')

    def test_create_table(self):
        with self.assertRaises(PermissionError):
            daos.create_table('test', None)
        with self.assertRaises(PermissionError):
            daos.create_table('test', self.user)
        table_creation_dao = daos.create_table('test', self.staff)
        self.assertEqual(table_creation_dao.table_detail_args(), (table_creation_dao._table.pk, 'test'))
        with self.assertRaises(IntegrityError):
            daos.create_table('test', self.staff)

    def test_table_creation_dao(self):
        table = models.Table.objects.get(name='dao_test')
        self.assertEqual(self.table_creation_dao._table, table)
        self.assertEqual(self.table_creation_dao._user, self.staff)
        self.assertEqual(self.table_creation_dao.site_ids, [None])
        self.assertEqual(self.table_creation_dao.is_owner, True)
        self.assertFalse(self.table_creation_dao.has_site_id_column())

    def test_table_creation_dao_permissions(self):
        with self.assertRaises(permissions_models.TablePermission.DoesNotExist):
            daos.TableCreationDAO(self.table_creation_dao._table, self.user)
        daos.TableCreationDAO(self.table_creation_dao._table, self.staff)

    def test_row_and_column_creation(self):
        with self.assertRaises(ValueError):
            with atomic():
                self.table_creation_dao.create_column('', ['a', 'b', 'c'])
        with atomic():
            self.table_creation_dao.create_column('column_1', ['a', 'b', 'c'])
        with self.assertRaises(IntegrityError):
            with atomic():
                self.table_creation_dao.create_column('column_1', ['a', 'b', 'c'])
        with atomic():
            self.table_creation_dao.create_column('column_2', ['1', '2', '3'])
        column_1 = models.Column.objects.get(name='column_1')
        column_2 = models.Column.objects.get(name='column_2')
        self.assertEqual(column_1.table_index, 0)
        self.assertEqual(column_2.table_index, 1)
        self.assertEqual(self.table_creation_dao.column_names(), ['column_1', 'column_2'])
        self.assertEqual(self.table_creation_dao.fields_to_row_key({'column_1': 0, 'column_2': 0}), 0)
        self.assertEqual(self.table_creation_dao.fields_to_row_key({'column_1': 1, 'column_2': 2}), 7)
        row_transformer = {'column_1': {'b': 1}, 'column_2': {'3': 2}}
        with self.assertRaises(IntegrityError):
            with atomic():
                self.table_creation_dao.create_row({'column_1': 'b', 'column_2': '3'}, row_transformer)
        with atomic():
            self.table_creation_dao.create_row({'column_1': 'b', 'column_2': '3', 'randomization_arm': '0'},
                                               row_transformer)
        row = models.Row.objects.get(table=self.table_creation_dao._table)
        self.assertEqual(row.randomization_arm, 0)
        self.assertEqual(row.key, 7)
        self.assertEqual(row.processed, False)
        self.assertEqual(row.processed_datetime, None)
        self.assertEqual(row.reservation, None)
        self.assertEqual(row.reservation_datetime, None)


class BasicTableMixin:
    def setUp(self):
        self.user = User.objects.create(username='test_not_staff')
        self.staff = User.objects.create(username='test_staff', is_staff=True)
        self.table_creation_dao = daos.create_table('dao_test', self.staff)
        self.table = self.table_creation_dao._table
        self.create_columns()
        row_transformer = {'column_1': {'b': 1}, 'column_2': {'1': 0, '2': 1, '3': 2}}
        self.table_creation_dao.create_row({'column_1': 'b', 'column_2': '3', 'randomization_arm': '1'},
                                           row_transformer)
        self.table_creation_dao.create_row({'column_1': 'b', 'column_2': '3',
                                            'randomization_arm': '1', 'processed': '0'},
                                           row_transformer)
        self.table_creation_dao.create_row({'column_1': 'b', 'column_2': '2', 'randomization_arm': '2'},
                                           row_transformer)
        self.table_creation_dao.create_row({'column_1': 'b', 'column_2': '1', 'randomization_arm': '2'},
                                           row_transformer)
        self.create_table_permissions()
        self.create_table_site_id_access()
        self.first_row = models.Row.objects.filter(table=self.table).first()

    def create_columns(self):
        self.table_creation_dao.create_column('column_1', ['a', 'b', 'c'])
        self.table_creation_dao.create_column('column_2', ['1', '2', '3'])

    def create_table_permissions(self):
        permissions_models.TablePermission.objects.create(table=self.table, user=self.user)

    def create_table_site_id_access(self):
        permissions_models.TableSiteIdAccess.objects.create(table=self.table, user=self.user, is_active=True)


class RowTestCase(BasicTableMixin, TestCase):
    def test_row_for_staff(self):
        table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
        expected_row_dao = daos.RowDAO(self.first_row, table_reservation_dao)
        actual_row_daos = list(table_reservation_dao.row_dao_iter(as_staff=False))
        self.assertEqual(expected_row_dao._row, actual_row_daos[0]._row)
        self.assertEqual(len(actual_row_daos), 4)
        self.assertEqual([], list(table_reservation_dao.row_dao_iter(as_staff=True)))

    def test_row_for_not_staff(self):
        table_reservation_dao = daos.TableReservationDAO(self.table, self.user)
        with self.assertRaises(PermissionError):
            daos.RowDAO(self.first_row, table_reservation_dao)
        self.assertEqual([], list(table_reservation_dao.row_dao_iter(as_staff=False)))
        self.assertEqual([], list(table_reservation_dao.row_dao_iter(as_staff=True)))

    def test_last_changed(self):
        row_dao = daos.RowDAO(self.first_row, self.table_creation_dao)
        self.assertEqual(row_dao.get_last_changed(), '')
        now = timezone.localtime()
        yesterday = now - timedelta(days=1)
        row_dao._row.processed_datetime = yesterday
        self.assertEquals(row_dao.get_last_changed(), yesterday.strftime("%m/%d/%Y %H:%M:%S %Z"))
        row_dao._row.reservation_datetime = now
        self.assertEquals(row_dao.get_last_changed(), now.strftime("%m/%d/%Y %H:%M:%S %Z"))
        row_dao._row.processed_datetime = None
        self.assertEquals(row_dao.get_last_changed(), now.strftime("%m/%d/%Y %H:%M:%S %Z"))
        row_dao._row.reservation_datetime = None
        self.assertEquals(row_dao.get_last_changed(), '')


class BulkTableMixin(BasicTableMixin):
    def create_bulk_rows(self, count):
        row_transformer = {'column_1': {'b': 1}, 'column_2': {'1': 0, '2': 1, '3': 2}}
        for i in range(count):
            self.table_creation_dao.create_row({'column_1': 'b', 'column_2': '3', 'randomization_arm': '1'},
                                               row_transformer)


class PatientIdTestCase(BulkTableMixin, TestCase):
    def test_patient_id_with_variable_row_counts(self):
        table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
        self.create_bulk_rows(100)
        self.assertEquals(table_reservation_dao._calculate_patient_id(None), 1001)
        self.create_bulk_rows(1000)
        self.assertEquals(table_reservation_dao._calculate_patient_id(None), 10001)
        self.create_bulk_rows(100)
        self.assertEquals(table_reservation_dao._calculate_patient_id(None), 10001)


class PatientIdReservationTestCase(BulkTableMixin, TestCase):
    def test_patient_id_with_reservations(self):
        self.create_bulk_rows(10)
        for i in range(10):
            table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
            row = table_reservation_dao.reserve_next_available_row({'column_1': 1, 'column_2': 2})
            self.assertEquals(row.patient_id, 1001)
            table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
            table_reservation_dao.cancel_my_reservation(row.pk)
        for i in range(10):
            table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
            row = table_reservation_dao.reserve_next_available_row({'column_1': 1, 'column_2': 2})
            self.assertEquals(row.patient_id, 1001 + i)
            table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
            table_reservation_dao.complete_my_reservation(row.pk)
        for i in range(10):
            table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
            row = table_reservation_dao.reserve_next_available_row({'column_1': 1, 'column_2': 2})
            self.assertEquals(row.patient_id, 1011)
            table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
            table_reservation_dao.cancel_my_reservation(row.pk)


class PatientIdReservationWithSiteIdTestCase(BasicTableMixin, TestCase):
    def create_columns(self):
        self.table_creation_dao.create_column('column_1', ['a', 'b', 'c'])
        self.table_creation_dao.create_column('column_2', ['1', '2', '3'], is_site_id_column=True)

    def create_bulk_rows(self, count):
        row_transformer = {'column_1': {'a': 0, 'b': 1, 'c': 2}, 'column_2': {'1': 0, '2': 1, '3': 2}}
        for key in '123':
            for i in range(count):
                self.table_creation_dao.create_row({'column_1': 'b', 'column_2': key, 'randomization_arm': '1'},
                                                   row_transformer)

    def test_patient_id_with_reservations(self):
        self.create_bulk_rows(10)
        for i in range(10):
            for id_offset in range(3):
                table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
                row = table_reservation_dao.reserve_next_available_row({'column_1': 1, 'column_2': id_offset})
                self.assertEquals(row.patient_id, 1000 * id_offset + 1001)
                table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
                table_reservation_dao.cancel_my_reservation(row.pk)
        for i in range(10):
            for id_offset in range(3):
                table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
                row = table_reservation_dao.reserve_next_available_row({'column_1': 1, 'column_2': id_offset})
                self.assertEquals(row.patient_id, 1000 * id_offset + 1001 + i)
                table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
                table_reservation_dao.complete_my_reservation(row.pk)
        for i in range(10):
            for id_offset in range(3):
                table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
                row = table_reservation_dao.reserve_next_available_row({'column_1': 1, 'column_2': id_offset})
                self.assertEquals(row.patient_id, 1000 * id_offset + 1011)
                table_reservation_dao = daos.TableReservationDAO(self.table, self.staff)
                table_reservation_dao.cancel_my_reservation(row.pk)


class TableReservationMixin(BasicTableMixin):
    def test_column_names_and_choices(self):
        table_reservation_dao = self.new_table_reservation_dao()
        column_names_and_choices = list(table_reservation_dao.column_names_and_choices_iter())
        self.assertEquals(column_names_and_choices, [('column_1', [('', ' '), ('0', 'a'), ('1', 'b'), ('2', 'c')]),
                                                     ('column_2', [('', ' '), ('0', '1'), ('1', '2'), ('2', '3')])])

    def reserve_next_available_row(self):
        table_reservation_dao = self.new_table_reservation_dao()
        with atomic():
            return table_reservation_dao.reserve_next_available_row({'column_1': 1, 'column_2': 2})

    def test_row_reservation(self):
        row = self.reserve_next_available_row()
        table_reservation_dao = self.new_table_reservation_dao()
        self.assertTrue(table_reservation_dao.has_reserved_row())
        self.assertEqual(row.pk, table_reservation_dao.my_reserved_row_pk())
        self.assertEquals(row.reservation, self.active_user())
        self.assertFalse(row.processed)
        row_dao = table_reservation_dao.get_reserved_row_dao()
        self.assertEquals(table_reservation_dao.get_row_values(row_dao._row), ['b', '3'])
        self.assertEquals(row_dao.get_values(), ['b', '3'])
        self.assertEquals(row_dao.is_table_owner, self.active_user() == self.staff)
        with atomic():
            table_reservation_dao.cancel_my_reservation(row.pk)

    def test_row_reservation_cancel(self):
        row = self.reserve_next_available_row()
        table_reservation_dao = self.new_table_reservation_dao()
        with atomic():
            row = table_reservation_dao.cancel_my_reservation(row.pk)
        self.assertIsNone(row.reservation)
        self.assertFalse(row.processed)

    def test_row_reservation_complete(self):
        row = self.reserve_next_available_row()
        table_reservation_dao = self.new_table_reservation_dao()
        with atomic():
            row = table_reservation_dao.complete_my_reservation(row.pk)
        self.assertEquals(row.reservation, self.active_user())
        self.assertTrue(row.processed)

    def new_table_reservation_dao(self):
        return daos.TableReservationDAO(self.table, self.active_user())

    def active_user(self):
        raise NotImplementedError


class StaffTableReservationTestCase(TableReservationMixin, TestCase):
    def active_user(self):
        return self.staff


class NonStaffTableReservationTestCase(TableReservationMixin, TestCase):
    def active_user(self):
        return self.user


class TableReservationWithSiteIdMixin(TableReservationMixin):
    def create_columns(self):
        self.table_creation_dao.create_column('column_1', ['a', 'b', 'c'])
        self.table_creation_dao.create_column('column_2', ['1', '2', '3'], is_site_id_column=True)

    def reserve_next_available_row(self):
        table_reservation_dao = self.new_table_reservation_dao()
        with atomic():
            return table_reservation_dao.reserve_next_available_row({'column_1': 1})

    def test_row_reservation(self):
        row = self.reserve_next_available_row()
        table_reservation_dao = self.new_table_reservation_dao()
        row_dao = table_reservation_dao.get_reserved_row_dao()
        self.assertEquals(row_dao.get_values(), ['b'])
        with atomic():
            table_reservation_dao.cancel_my_reservation(row.pk)

    def test_column_names_and_choices(self):
        table_reservation_dao = self.new_table_reservation_dao()
        column_names_and_choices = list(table_reservation_dao.column_names_and_choices_iter())
        self.assertEquals(column_names_and_choices, [('column_1', [('', ' '), ('0', 'a'), ('1', 'b'), ('2', 'c')])])

    def active_user(self):
        raise NotImplementedError


class NonStaffTableReservationTestCaseWithSiteId(TableReservationWithSiteIdMixin, TestCase):
    def active_user(self):
        return self.user

    def create_table_site_id_access(self):
        permissions_models.TableSiteIdAccess.objects.create(table=self.table, user=self.user, site_id=2, is_active=True)


class NonStaffTableReservationTestCaseWithMultipleSiteIds(TableReservationWithSiteIdMixin, TestCase):
    def active_user(self):
        return self.user

    def create_table_site_id_access(self):
        permissions_models.TableSiteIdAccess.objects.create(table=self.table, user=self.user, site_id=1, is_active=True)
        permissions_models.TableSiteIdAccess.objects.create(table=self.table, user=self.user, site_id=2, is_active=True)

    def reserve_next_available_row(self):
        table_reservation_dao = self.new_table_reservation_dao()
        with atomic():
            return table_reservation_dao.reserve_next_available_row({'column_1': 1, 'column_2': 1})

    def test_other_reservation_options(self):
        table_reservation_dao = self.new_table_reservation_dao()
        with atomic():
            row = table_reservation_dao.reserve_next_available_row({'column_1': 1, 'column_2': 2})
        for column_2_value in (1, 2):
            table_reservation_dao = self.new_table_reservation_dao()
            with self.assertRaises(PermissionError):
                with atomic():
                    table_reservation_dao.reserve_next_available_row({'column_1': 1, 'column_2': column_2_value})
        with atomic():
            table_reservation_dao.cancel_my_reservation(row.pk)
        with self.assertRaises(LookupError):
            table_reservation_dao = self.new_table_reservation_dao()
            with atomic():
                table_reservation_dao.reserve_next_available_row({'column_1': 1, 'column_2': 0})

    def test_column_names_and_choices(self):
        table_reservation_dao = self.new_table_reservation_dao()
        column_names_and_choices = list(table_reservation_dao.column_names_and_choices_iter())
        self.assertEquals(column_names_and_choices, [('column_1', [('', ' '), ('0', 'a'), ('1', 'b'), ('2', 'c')]),
                                                     ('column_2', [('', ' '), ('1', '2'), ('2', '3')])])


class StaffTableReservationTestCaseWithSiteId(TableReservationWithSiteIdMixin, TestCase):
    def create_table_site_id_access(self):
        permissions_models.TableSiteIdAccess.objects.filter(table=self.table, user=self.staff).update(site_id=2)

    def active_user(self):
        return self.staff


class InvalidStaffTableReservationTestCaseWithSiteId(TableReservationWithSiteIdMixin, TestCase):
    def setUp(self):
        super().setUp()

    def test_row_reservation(self):
        with self.assertRaises(LookupError):
            self.reserve_next_available_row()

    def test_row_reservation_cancel(self):
        pass

    def test_row_reservation_complete(self):
        pass

    def test_column_names_and_choices(self):
        pass

    def active_user(self):
        return self.staff


class StaffTableAppendTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='test_not_staff')
        self.staff = User.objects.create(username='test_staff', is_staff=True)
        table_creation_dao = daos.create_table('dao_test', self.staff)
        self.table = table_creation_dao._table
        table_creation_dao.create_column('column_1', ['a', 'b', 'c'], is_site_id_column=True)
        table_creation_dao.create_column('column_2', ['1', '2', '3'])
        row_transformer = {'column_1': {'b': 1}, 'column_2': {'3': 2}}
        table_creation_dao.create_row({'column_1': 'b', 'column_2': '3', 'randomization_arm': '1'}, row_transformer)
        table_creation_dao.create_row({'column_1': 'b', 'column_2': '3', 'randomization_arm': '1'}, row_transformer)
        self.table_append_dao = daos.TableCreationDAO(self.table, self.staff)

    def test_update_site_column(self):
        with atomic():
            with self.assertRaises(ValueError):
                self.table_append_dao.update_site_id_column(['a', 'b'])
            with self.assertRaises(ValueError):
                self.table_append_dao.update_site_id_column(['a', 'b', 'd', 'e'])
        self.table_append_dao.update_site_id_column(['a', 'b', 'c', 'd', 'e'])

    def test_column_validation(self):
        with self.assertRaises(KeyError):
            column_values = {'column_1': ['d']}
            self.table_append_dao.validate_potential_column_values_against_existing(column_values)
        with self.assertRaises(KeyError):
            column_values = {'column_1': ['c'], 'column_2': ['1', '2', '3']}
            self.table_append_dao.validate_potential_column_values_against_existing(column_values)
        with self.assertRaises(KeyError):
            column_values = {'column_1': ['d'], 'column_2': ['1', '2', '3', '4']}
            self.table_append_dao.validate_potential_column_values_against_existing(column_values)
        with self.assertRaises(KeyError):
            column_values = {'column_1': ['d'], 'column_2': ['1', '2', '3'], 'column_3': ['T', 'F']}
            self.table_append_dao.validate_potential_column_values_against_existing(column_values)
        column_values = {'column_1': ['d'], 'column_2': ['1', '2', '3']}
        self.table_append_dao.validate_potential_column_values_against_existing(column_values)


class TableColumnRenameMixin:
    def setUp(self):
        self.user = User.objects.create(username='test_not_staff')
        self.staff = User.objects.create(username='test_staff', is_staff=True)
        table_creation_dao = daos.create_table('dao_test', self.staff)
        self.table = table_creation_dao._table
        table_creation_dao.create_column('column_1', ['a', 'b', 'c'])
        table_creation_dao.create_column('column_2', ['1', '2', '3'], is_site_id_column=self.has_site_id())
        row_transformer = {'column_1': {'b': 1}, 'column_2': {'3': 2}}
        table_creation_dao.create_row({'column_1': 'b', 'column_2': '3', 'randomization_arm': '1'}, row_transformer)
        table_creation_dao.create_row({'column_1': 'b', 'column_2': '3', 'randomization_arm': '1'}, row_transformer)
        self.table_modify_dao = daos.TableCreationDAO(self.table, self.staff)

    def test_column_name_validation(self):
        input_validators.validate_column_names(['a', 'b', 'c'])
        with self.assertRaises(ValueError):
            input_validators.validate_column_names(['a', 'a', 'c'])
        with self.assertRaises(ValueError):
            input_validators.validate_column_names(['a', '', 'c'])
        with self.assertRaises(ValueError):
            input_validators.validate_column_names(['a', 'b&', 'c'])
        with self.assertRaises(ValueError):
            input_validators.validate_column_names(['a', 'b"', 'c'])
        with self.assertRaises(ValueError):
            input_validators.validate_column_names(['a', 'b,', 'c'])
        self.table_modify_dao._validate_potential_column_names({'col_0': 'a', 'col_1': 'b'})
        with self.assertRaises(ValueError):
            self.table_modify_dao._validate_potential_column_names({'col_0': 'a', 'col_1': 'b<>'})
        with self.assertRaises(ValueError):
            self.table_modify_dao._validate_potential_column_names({'col_0': 'a<>', 'col_1': 'b'})

    def has_site_id(self):
        return NotImplementedError


class TableColumnRenameTestCaseNoSiteId(TableColumnRenameMixin, TestCase):
    def has_site_id(self):
        return False

    def test_column_rename(self):
        self.table_modify_dao.rename_columns_and_values({'col_0': 'col_a', 'col_1': 'col_b',
                                                         'col_0_0': 'd', 'col_0_1': 'e', 'col_0_2': 'f',
                                                         'col_1_0': '4', 'col_1_1': '5', 'col_1_2': '6',
                                                         'arm_1': 'A', 'arm_2': 'B'})
        columns = list(models.Column.objects.filter(table=self.table))
        self.assertEquals(len(columns), 2)
        self.assertEquals(columns[0].name, 'col_a')
        self.assertEquals(columns[1].name, 'col_b')
        self.assertEquals(columns[0].potential_values, 'd,e,f')
        self.assertEquals(columns[1].potential_values, '4,5,6')
        self.assertEquals(self.table.arm_1, 'A')
        self.assertEquals(self.table.arm_2, 'B')


class TableColumnRenameTestCaseWithSiteId(TableColumnRenameMixin, TestCase):
    def has_site_id(self):
        return True

    def test_column_rename(self):
        self.table_modify_dao.rename_columns_and_values({'col_0': 'col_a', 'col_1': 'col_b',
                                                         'col_0_0': 'd', 'col_0_1': 'e', 'col_0_2': 'f',
                                                         'col_1_0': '4', 'col_1_1': '5', 'col_1_2': '6',
                                                         'arm_1': 'A', 'arm_2': 'B'})
        column = models.Column.objects.get(table=self.table)
        site_id_column = models.SiteIdColumn.objects.get(table=self.table)
        self.assertEquals(column.name, 'col_a')
        self.assertEquals(site_id_column.name, 'col_b')
        self.assertEquals(column.potential_values, 'd,e,f')
        self.assertEquals(site_id_column.potential_values, '4,5,6')
        self.assertEquals(self.table_modify_dao.get_arm_name(1), 'A')
        self.assertEquals(self.table_modify_dao.get_arm_name(2), 'B')
        with self.assertRaises(ValueError):
            self.table_modify_dao.get_arm_name(3)
        with self.assertRaises(ValueError):
            self.table_modify_dao.get_arm_name('A')
        with self.assertRaises(ValueError):
            self.table_modify_dao.get_arm_name(0)
