def table_tag(s):
    return f'<table>{s}</table>'


def tbody_tag(s):
    return f'<tbody>{s}</tbody>'


def thead_tag(s):
    return f'<thead>{s}</thead>'


def tr_tag(s):
    return f'<tr>{s}</tr>'


def td_tag(s, **kwargs):
    extra = ''.join(f' {key}="{kwargs[key]}"' for key in kwargs)
    return f'<td{extra}>{s}</td>'


def input_tag(name, value, **kwargs):
    extra = ''.join(f' {key}="{kwargs[key]}"' for key in kwargs)
    return f'<input name="{name}" value="{value}"{extra}>'


def ths(strings):
    return ''.join(f'<th>{s}</th>' for s in strings)


def tds(strings):
    return ''.join(f'<td>{s}</td>' for s in strings)


class HtmlTableGenerator:
    def as_html_table(self):
        return table_tag(self.get_html_table_header() + self.get_html_table_body())

    def get_html_table_header(self):
        raise NotImplementedError

    def get_html_table_body(self):
        raise NotImplementedError

    @staticmethod
    def get_site_id_columns(table_dao):
        return [table_dao.site_id_column_name()] if table_dao.has_site_id_column() else []
