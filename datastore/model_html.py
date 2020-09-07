from django.utils.translation import gettext
from randomizer.html_utils import HtmlTableGenerator, thead_tag, tbody_tag, tr_tag, td_tag, input_tag, tds, ths


class TableHtml(HtmlTableGenerator):
    def __init__(self, table_dao, as_staff=True):
        self.table_dao = table_dao
        self.as_owner = self.table_dao.is_owner and not as_staff

    def get_html_table_header(self):
        core_columns = self.get_site_id_columns(self.table_dao) + self.table_dao.column_names()
        if self.as_owner:
            columns = core_columns + ['Randomization Arm', 'Reservation Action', 'Reserved By', 'Last Changed']
        else:
            columns = [gettext('PatientId')] + core_columns + [gettext('RandomizationArm')]
        return thead_tag(tr_tag(ths(columns)))

    def get_html_table_body(self):
        rows_html = ''
        for row_dao in self.table_dao.row_dao_iter(not self.as_owner):
            if self.as_owner and not row_dao.is_locked_for_reservation():
                continue
            row_html = RowHtml(row_dao, self)
            rows_html += row_html.as_html_tr(self.as_owner)
        if not rows_html:
            column_count = 2 + (1 if self.table_dao.has_site_id_column() else 0) + len(self.table_dao.column_names())
            td_text = gettext('NoRowsReservedYet')
            if self.as_owner:
                td_text = 'No rows currently locked for reservation'
                column_count += 2
            rows_html = tr_tag(td_tag(td_text, colspan=column_count))
        return tbody_tag(rows_html)


class RowHtml(HtmlTableGenerator):
    def __init__(self, row_dao, table_html):
        self._table_html = table_html
        self._row_dao = row_dao

    def get_html_table_header(self):
        return self._table_html.get_html_table_header()

    def get_html_table_body(self):
        return tbody_tag(self.as_html_tr(as_owner=False))

    def as_html_tr(self, as_owner=False):
        td_values = []
        if not as_owner:
            td_values += [self._row_dao.get_patient_id()]
        td_values += self._get_site()
        td_values += self._row_dao.get_values() + [self._row_dao.get_randomization_arm()]
        if as_owner:
            td_values += self._get_processing_status()
        return tr_tag(tds(td_values))

    def _get_site(self):
        site = self._row_dao.get_site()
        if site is not None:
            return [site]
        return []

    def _get_processing_status(self):
        process_action = self._get_process_action_td_value()
        return [process_action, self._row_dao.get_reservation_username(), self._row_dao.get_last_changed()]

    def _get_process_action_td_value(self):
        row_pk = self._row_dao.get_pk()
        complete = input_tag(f'row_{row_pk}', 'Complete', type='submit')
        cancel = input_tag(f'row_{row_pk}', 'Cancel', type='submit')
        return complete + cancel


class ColumnUpdateHtml(HtmlTableGenerator):
    def __init__(self, table_reservation_dao, previous_values=None):
        self.table_reservation_dao = table_reservation_dao
        self.previous_values = previous_values
        self.choice_count = None

    def get_html_table_header(self):
        return thead_tag(tr_tag(ths(['Column', 'Renamed Column',
                                     'Column Value', 'Renamed Column Value'])))

    def get_html_table_body(self):
        rows_html = ''
        column_iter = self.table_reservation_dao.column_names_and_choices_iter(include_site_column=True)
        for column_index, (column_name, column_choices) in enumerate(column_iter):
            self.choice_count = len(column_choices) - 1
            for choice_index, (_, choice_name) in enumerate(column_choices[1:]):
                rows_html += self.get_tr(column_name, column_index, choice_name, choice_index)
        rows_html += self.get_tr_for_arm(1)
        rows_html += self.get_tr_for_arm(2)
        return tbody_tag(rows_html)

    def get_tr(self, column_name, column_index, choice_name, choice_index):
        first_column = ''
        second_column = ''
        if choice_index == 0:
            column_name_for_input = column_name
            if self.previous_values:
                column_name_for_input = self.previous_values[f'col_{column_index}']
            column_input = input_tag(f'col_{column_index}', column_name_for_input)
            first_column = td_tag(column_name, rowspan=self.choice_count)
            second_column = td_tag(column_input, rowspan=self.choice_count)
        choice_name_for_input = choice_name
        if self.previous_values:
            choice_name_for_input = self.previous_values[f'col_{column_index}_{choice_index}']
        column_choice_input = input_tag(f'col_{column_index}_{choice_index}', choice_name_for_input)
        return tr_tag(first_column + second_column + tds([choice_name, column_choice_input]))

    def get_tr_for_arm(self, arm):
        first_column = td_tag('Randomization Arm', rowspan=2, colspan=2) if arm == 1 else ''
        arm_name = self.table_reservation_dao.get_arm_name(arm)
        arm_name_input = input_tag(f'arm_{arm}', arm_name)
        return tr_tag(first_column +  tds([arm_name, arm_name_input]))
