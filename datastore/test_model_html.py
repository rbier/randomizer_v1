from django.contrib.auth.models import User
from django.test import TestCase
from . import model_html, daos
from permissions import models as permissions_models


class TableHtmlTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create(username='test', is_staff=True)
        self.user = User.objects.create(username='test2')
        table_creation_dao = daos.create_table('test', self.owner)
        self.table = table_creation_dao._table
        permissions_models.TablePermission.objects.create(table=self.table, user=self.user)
        permissions_models.TableSiteIdAccess.objects.create(table=self.table, user=self.user, is_active=True)
        row_transformer = {}
        for i in range(3):
            table_creation_dao.create_column(name=f'col{i + 1}', value_options=[0, 1, 2, 3])
            row_transformer[f'col{i + 1}'] = {0: 0, 1: 1, 2: 2, 3: 3}
        table_creation_dao.create_row({'col1': 1, 'col2': 2, 'col3': 3, 'randomization_arm': 1}, row_transformer)
        table_creation_dao.create_row({'col1': 0, 'col2': 0, 'col3': 1, 'randomization_arm': 1}, row_transformer)
        table_creation_dao.create_row({'col1': 0, 'col2': 0, 'col3': 0, 'randomization_arm': 1}, row_transformer)

    def test_html_header(self):
        table_html = model_html.TableHtml(daos.TableDAO(table=self.table, user=self.owner), as_staff=False)
        self.assertEqual(table_html.get_html_table_header(),
                         '<thead><tr>'
                         '<th>col1</th><th>col2</th><th>col3</th><th>Randomization Arm</th>'
                         '<th>Reservation Action</th><th>Reserved By</th><th>Last Changed</th>'
                         '</tr></thead>')
        table_html = model_html.TableHtml(daos.TableDAO(table=self.table, user=self.user))
        self.assertEqual(table_html.get_html_table_header(),
                         '<thead><tr>'
                         '<th>Patient Id</th><th>col1</th><th>col2</th><th>col3</th><th>Randomization Arm</th>'
                         '</tr></thead>')

    def test_html_body(self):
        table_html = model_html.TableHtml(daos.TableDAO(table=self.table, user=self.owner), as_staff=False)
        self.assertEqual(table_html.get_html_table_body(),
                         '<tbody><tr><td colspan="7">No rows currently locked for reservation</td></tr></tbody>')
        table_reservation_dao = daos.TableReservationDAO(table=self.table, user=self.user)
        table_html = model_html.TableHtml(table_reservation_dao)
        self.assertEqual(table_html.get_html_table_body(),
                         '<tbody><tr><td colspan="5">You have not reserved any rows yet.</td></tr></tbody>')
        row = table_reservation_dao.reserve_next_available_row({'col1': 0, 'col2': 0, 'col3': 0})
        table_html = model_html.TableHtml(daos.TableDAO(table=self.table, user=self.owner), as_staff=False)
        self.assertTrue(table_html.get_html_table_body().startswith(
            '<tbody><tr><td>0</td><td>0</td><td>0</td><td>1</td><td>'))
        table_reservation_dao = daos.TableReservationDAO(table=self.table, user=self.user)
        table_reservation_dao.complete_my_reservation(row.pk)
        table_html = model_html.TableHtml(daos.TableReservationDAO(table=self.table, user=self.user), as_staff=True)
        self.assertEqual(table_html.get_html_table_body(),
                         '<tbody><tr><td>1001</td><td>0</td><td>0</td><td>0</td><td>1</td></tr></tbody>')


class ColumnUpdateHtmlTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create(username='test', is_staff=True)
        table_creation_dao = daos.create_table('test', self.owner)
        self.table = table_creation_dao._table
        table_creation_dao.create_column('column_1', ['a', 'b', 'c'])
        table_creation_dao.create_column('column_2', ['1', '2', '3'])

    def test_html_header(self):
        column_update_html = model_html.ColumnUpdateHtml(daos.TableReservationDAO(table=self.table, user=self.owner))
        self.assertEqual(column_update_html.get_html_table_header(),
                         '<thead><tr>'
                         '<th>Column</th><th>Renamed Column</th><th>Column Value</th><th>Renamed Column Value</th>'
                         '</tr></thead>')

    def test_html_body(self):
        column_update_html = model_html.ColumnUpdateHtml(daos.TableReservationDAO(table=self.table, user=self.owner))
        self.assertEqual(column_update_html.get_html_table_body(),
                         '<tbody>'
                         '<tr><td rowspan="3">column_1</td><td rowspan="3"><input name="col_0" value="column_1"></td>'
                         '<td>a</td><td><input name="col_0_0" value="a"></td></tr>'
                         '<tr><td>b</td><td><input name="col_0_1" value="b"></td></tr>'
                         '<tr><td>c</td><td><input name="col_0_2" value="c"></td></tr>'
                         '<tr><td rowspan="3">column_2</td><td rowspan="3"><input name="col_1" value="column_2"></td>'
                         '<td>1</td><td><input name="col_1_0" value="1"></td></tr>'
                         '<tr><td>2</td><td><input name="col_1_1" value="2"></td></tr>'
                         '<tr><td>3</td><td><input name="col_1_2" value="3"></td></tr>'
                         '<tr><td rowspan="2" colspan="2">Randomization Arm</td>'
                         '<td>1</td><td><input name="arm_1" value="1"></td></tr>'
                         '<tr><td>2</td><td><input name="arm_2" value="2"></td></tr>'
                         '</tbody>')
