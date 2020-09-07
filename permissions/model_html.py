from randomizer.html_utils import HtmlTableGenerator, thead_tag, tbody_tag, tr_tag, td_tag, input_tag, tds, ths
from . import daos

class ActivationCodeHtml(HtmlTableGenerator):
    def __init__(self, table_dao):
        self.table_dao = table_dao

    def get_html_table_header(self):
        columns = self.get_site_id_columns(self.table_dao) + ['Activation Code']
        return thead_tag(tr_tag(ths(columns)))

    def get_html_table_body(self):
        rows_html = ''
        for activation_code_data in self.table_dao.get_activation_code_data():
            rows_html += tr_tag(tds(activation_code_data))
        return tbody_tag(rows_html)


class TableSiteIdAccessHtml(HtmlTableGenerator):
    def __init__(self, table_site_id_access_query):
        self.table_site_id_access_query = table_site_id_access_query

    def get_html_table_header(self):
        return thead_tag(tr_tag(ths(['Table', 'User', 'Site Id', 'Approve'])))

    def get_html_table_body(self):
        rows_html = ''
        for access in self.table_site_id_access_query:
            site = daos.get_site(access)
            submit = input_tag(f'site_{access.pk}', 'Approve', type='submit')
            rows_html += tr_tag(tds([access.table.name, access.user, site, submit]))
        if not rows_html:
            rows_html = tr_tag(td_tag('No study access requests pending approval.', colspan=4))
        return tbody_tag(rows_html)
