from django.contrib.auth.models import User
from django.core.validators import ValidationError
from django.db.transaction import atomic
from django.db.utils import IntegrityError
from django.test import TestCase
from . import model_html
from . import models
from datastore import daos


class StaffTableReservationWithSiteIdTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='test_not_staff')
        self.staff = User.objects.create(username='test_staff', is_staff=True)
        self.table_creation_dao = daos.create_table('dao_test', self.staff)
        self.table = self.table_creation_dao._table
        self.table_creation_dao.create_column('column_1', ['a', 'b', 'c'])
        self.table_creation_dao.create_column('column_2', ['1', '2', '3'], is_site_id_column=True)
        models.TablePermission.objects.create(table=self.table, user=self.user)
        models.TableSiteIdAccess.objects.create(table=self.table, user=self.user, is_active=False, site_id=2)

    def test_activation_codes(self):
        with atomic():
            models.ActivationCode.objects.create(table=self.table, code='10000000', site_id=1)
            models.ActivationCode.objects.create(table=self.table, code='10000001', site_id=2)
            with atomic():
                with self.assertRaises(IntegrityError):
                    models.ActivationCode.objects.create(table=self.table, code='10000002', site_id=2)
        with self.assertRaises(ValidationError):
            models.ActivationCode.activation_code_validator('123456789')
        with self.assertRaises(ValidationError):
            models.ActivationCode.activation_code_validator('1234567')
        with self.assertRaises(PermissionError):
            daos.TableDAO(self.table, self.user)
        table_dao = daos.TableDAO(self.table, self.staff)
        self.assertEqual(table_dao.get_activation_code_data(), [('2', '10000000'), ('3', '10000001')])
        with atomic():
            models.ActivationCode.objects.filter(table=self.table).delete()
            self.table_creation_dao.create_activation_codes()
        table_dao = daos.TableDAO(self.table, self.staff)
        self.assertEqual(len(table_dao.get_activation_code_data()), 3)


class StaffTableAppendTestCase(TestCase):
    def setUp(self):
        self.staff = User.objects.create(username='test_staff', is_staff=True)
        table_creation_dao = daos.create_table('dao_test', self.staff)
        self.table = table_creation_dao._table
        table_creation_dao.create_column('column_1', ['a', 'b', 'c'], is_site_id_column=True)
        table_creation_dao.create_column('column_2', ['1', '2', '3'])
        self.table_append_dao = daos.TableCreationDAO(self.table, self.staff)

    def test_update_activation_codes(self):
        with atomic():
            self.table_append_dao.create_activation_codes()
        self.assertEqual(models.ActivationCode.objects.count(), 3)
        self.table_append_dao.update_site_id_column(['a', 'b', 'c', 'd', 'e'])
        self.table_append_dao.create_activation_codes()
        self.assertEqual(models.ActivationCode.objects.count(), 5)


class MultisiteActivationCodeHtmlTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create(username='test', is_staff=True)
        table_creation_dao = daos.create_table('test', self.owner)
        self.table = table_creation_dao._table
        table_creation_dao.create_column('column_1', ['a', 'b', 'c'])
        table_creation_dao.create_column('column_2', ['1', '2', '3'], is_site_id_column=True)
        models.ActivationCode.objects.create(table=self.table, code='10000000', site_id=1)
        models.ActivationCode.objects.create(table=self.table, code='10000001', site_id=2)

    def test_html_header(self):
        activation_code_html = model_html.ActivationCodeHtml(daos.TableDAO(table=self.table, user=self.owner))
        self.assertEqual(activation_code_html.get_html_table_header(),
                         '<thead><tr>'
                         '<th>column_2</th>'
                         '<th>Activation Code</th>'
                         '</tr></thead>')

    def test_html_body(self):
        activation_code_html = model_html.ActivationCodeHtml(daos.TableDAO(table=self.table, user=self.owner))
        self.assertEqual(activation_code_html.get_html_table_body(),
                         '<tbody>'
                         '<tr><td>2</td><td>10000000</td></tr>'
                         '<tr><td>3</td><td>10000001</td></tr>'
                         '</tbody>')


class SingleSiteActivationCodeHtmlTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create(username='test', is_staff=True)
        table_creation_dao = daos.create_table('test', self.owner)
        self.table = table_creation_dao._table
        table_creation_dao.create_column('column_1', ['a', 'b', 'c'])
        table_creation_dao.create_column('column_2', ['1', '2', '3'])
        models.ActivationCode.objects.create(table=self.table, code='10000002')

    def test_html_header(self):
        activation_code_html = model_html.ActivationCodeHtml(daos.TableDAO(table=self.table, user=self.owner))
        self.assertEqual(activation_code_html.get_html_table_header(),
                         '<thead><tr><th>Activation Code</th></tr></thead>')

    def test_html_body(self):
        activation_code_html = model_html.ActivationCodeHtml(daos.TableDAO(table=self.table, user=self.owner))
        self.assertEqual(activation_code_html.get_html_table_body(),
                         '<tbody><tr><td>10000002</td></tr></tbody>')


