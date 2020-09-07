from django import forms
from django.http import Http404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext
from django.views.generic import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormView
from . import daos
from . import model_html
from . import models
from . import table_creation
from . import input_validators
from permissions import daos as permissions_daos
from permissions import model_html as permissions_html


class ReserveRowForm(forms.Form):
    def __init__(self, table_reservation_dao, data=None):
        super().__init__(data)
        self.table_reservation_dao = table_reservation_dao
        self.initialize_fields()

    def initialize_fields(self):
        for column_name, column_choices in self.table_reservation_dao.column_names_and_choices_iter():
            self.fields[column_name] = forms.ChoiceField(choices=column_choices)

    def reserve_next_available_row(self):
        if not super().is_valid():
            raise ValueError(gettext('FormDataIncompleteError'))
        cleaned_integer_data = {x: int(self.cleaned_data[x]) for x in self.cleaned_data}
        self.table_reservation_dao.reserve_next_available_row(cleaned_integer_data)


class UploadTableForm(forms.Form):
    name = forms.CharField()
    site_id_field = forms.CharField(required=False,
                                    help_text='Leave blank if this study is a single site study. '
                                              'Otherwise, please provide the name of the column used for '
                                              'specifying the site of a given patient.')
    csv = forms.FileField()
    table_creator = None

    def validate_name(self):
        try:
            input_validators.validate_table_name(self.cleaned_data['name'])
        except Exception as e:
            self.add_error('name', e)

    def validate_csv(self):
        try:
            table_creation.validate_table_data(self.table_creator.csv_file, self.table_creator.site_id_field)
        except (ValueError, KeyError) as e:
            self.add_error('csv', f'File read error: {e}')

    def initialize_table_creator(self):
        try:
            self.table_creator.calculate_column_value_options_and_row_count()
        except (ValueError, KeyError) as e:
            self.add_error('csv', f'File read error: {e}')

    def is_valid(self):
        if not super().is_valid():
            return False
        self.validate_name()
        if not self.errors:
            self.table_creator = table_creation.CSVTableCreator(self.cleaned_data['csv'], self.cleaned_data['name'],
                                                                self.cleaned_data['site_id_field'], self.user)
        if not self.errors:
            self.validate_csv()
        if not self.errors:
            self.initialize_table_creator()
        return not self.errors

    def upload_table(self):
        return self.table_creator.create_table()


class UploadTableView(FormView):
    template_name = 'randomization_table_upload.html'
    form_class = UploadTableForm

    def form_valid(self, form):
        table_creation_dao = form.upload_table()
        return HttpResponseRedirect(reverse('table_detail', args=table_creation_dao.table_detail_args()))

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.user = self.request.user
        return form


class MyTablesView(ListView):
    model = models.Table

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        can_create_table = table_creation.user_can_create_tables(self.request.user)
        if not can_create_table and len(self.object_list) == 1:
            table = self.object_list.first()
            if not permissions_daos.user_has_table_access(self.request.user, table):
                return HttpResponseRedirect(reverse('study_access'))
            return HttpResponseRedirect(reverse('table_detail', args=(table.pk, table.slug())))
        context = self.get_context_data(user_can_create_tables=can_create_table)
        return self.render_to_response(context)

    def get_queryset(self):
        return models.Table.objects.filter(tablepermission__user=self.request.user, is_hidden=False).order_by('name')


class TableViewMixin:
    model = models.Table

    def __init__(self):
        super().__init__()
        self.table_reservation_dao = None
        self.object = None
        self.request = None

    def init_table(self, request, table_pk):
        self.object = models.Table.objects.get(pk=table_pk)
        self.request = request
        if self.object.is_hidden:
            raise Http404
        try:
            self.table_reservation_dao = daos.TableReservationDAO(self.object, request.user)
        except Exception:
            raise Http404

    def get(self, request, *args, **kwargs):
        self.init_table(request, kwargs['pk'])
        return self.validate_slug(self.get_core, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            self.init_table(request, kwargs['pk'])
            return self.validate_slug(self.post_core, *args, **kwargs)
        except Exception as e:
            return self.post_error(e)

    def validate_slug(self, fn, *args, **kwargs):
        if self.object.slug() != kwargs['table_slug']:
            return HttpResponseRedirect(self.redirect_url())
        return fn(*args, **kwargs)

    def redirect_url(self):
        return reverse(self.view_name(), args=(self.object.pk, self.object.slug()))

    @classmethod
    def redirect_url_for_table(cls, table):
        return reverse(cls.view_name(), args=(table.pk, table.slug()))

    def table_options(self):
        options = {'is_owner': False,
                   'user_can_create_tables': table_creation.user_can_create_tables(self.request.user)}
        if self.table_reservation_dao.is_owner:
            options['is_owner'] = True
            if not isinstance(self, TableDetailView):
                options['table_home'] = TableDetailView.redirect_url_for_table(self.object)
            if not isinstance(self, TableColumnsView):
                options['table_columns'] = TableColumnsView.redirect_url_for_table(self.object)
            if not isinstance(self, TableAppendView):
                if self.table_reservation_dao.has_site_id_column():
                    options['table_append'] = TableAppendView.redirect_url_for_table(self.object)
        return options

    def get_core(self, *args, **kwargs):
        raise NotImplementedError

    def post_core(self, *args, **kwargs):
        raise NotImplementedError

    def post_error(self, error):
        raise NotImplementedError

    @staticmethod
    def view_name():
        raise NotImplementedError


class TableDetailView(TableViewMixin, DetailView):
    def __init__(self):
        super().__init__()
        self.table_reservation_dao = None
        self.object = None

    @staticmethod
    def view_name():
        return 'table_detail'

    def get_core(self, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def post_core(self, *args, **kwargs):
        if 'confirm' in self.request.POST:
            kwargs['success_message'], kwargs['email_message'] = self._post_complete_reservation(**kwargs)
        elif 'cancel' in self.request.POST:
            kwargs['success_message'] = self._post_cancel_reservation(**kwargs)
        elif 'admin' in self.request.POST:
            kwargs['success_message'] = self._post_admin_override(**kwargs)
        else:
            kwargs['success_message'] = self._post_reserve_next_row()
        return self.get(self.request, *args, **kwargs)

    def post_error(self, error):
        context = self.get_context_data(error=error)
        context['action'] = 'confirmation' if 'confirm' in self.request.POST \
            else 'cancellation' if 'cancel' in self.request.POST \
            else 'override' if 'admin' in self.request.POST else 'reservation'
        return self.render_to_response(context)

    def _post_reserve_next_row(self):
        form = ReserveRowForm(self.table_reservation_dao, self.request.POST)
        form.reserve_next_available_row()

    def _post_complete_reservation(self, **kwargs):
        row = self.table_reservation_dao.complete_my_reservation(self.request.POST['row'])
        arm_name = self.table_reservation_dao.get_arm_name(row.randomization_arm)
        success_message = gettext('CompleteReservationSuccess').format(row.patient_id)
        email_message = gettext('CompleteReservationEmail').format(row.patient_id, arm_name, row.table.name)
        return success_message, email_message

    def _post_cancel_reservation(self, **kwargs):
        self.table_reservation_dao.cancel_my_reservation(self.request.POST['row'])
        return gettext('ReservationCancel')

    def _post_admin_override(self, **kwargs):
        if not self.table_reservation_dao.is_owner:
            raise PermissionError('Invalid override permissions')
        row_pk, action = self._extract_row_and_action()
        if action == 'Complete':
            return self._post_complete_override(row_pk, **kwargs)
        if action == 'Cancel':
            return self._post_cancel_override(row_pk, **kwargs)
        raise KeyError('Invalid reservation override')

    def _post_complete_override(self, row_pk, **kwargs):
        self.table_reservation_dao.complete_override_reservation(row_pk)
        return gettext('CompleteReservationSuccessAnonymous')

    def _post_cancel_override(self, row_pk, **kwargs):
        self.table_reservation_dao.cancel_override_reservation(row_pk)
        return gettext('ReservationCancel')

    def _extract_row_and_action(self):
        for key in self.request.POST:
            if key.startswith('row_'):
                return int(key[4:]), self.request.POST[key]
        return None, None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        as_staff = 'as_staff' in self.request.GET
        table_html = model_html.TableHtml(self.table_reservation_dao, as_staff)
        context['html_table'] = table_html.as_html_table()
        context.update(self.table_options())
        if as_staff or not context['is_owner']:
            self.populate_context_data_for_reservations(context)
        else:
            activation_code_html = permissions_html.ActivationCodeHtml(self.table_reservation_dao)
            context['activation_code_html_table'] = activation_code_html.as_html_table()
        return context

    def populate_context_data_for_reservations(self, context):
        context['has_reserved_row'] = self.table_reservation_dao.has_reserved_row()
        if context['has_reserved_row']:
            try:
                table_html = model_html.TableHtml(self.table_reservation_dao)
                row_dao = self.table_reservation_dao.get_reserved_row_dao()
                row_html = model_html.RowHtml(row_dao, table_html)
                context['row_pk'] = self.table_reservation_dao.my_reserved_row_pk()
                context['row_table'] = row_html.as_html_table()
            except PermissionError:
                pass
        else:
            context['form'] = ReserveRowForm(self.table_reservation_dao)

    def get_queryset(self):
        return super().get_queryset().prefetch_related('row_set', 'column_set')


class TableColumnsView(TableViewMixin, DetailView):
    template_name_suffix = '_columns'

    def __init__(self):
        super().__init__()
        self.submitted_values = None

    def get_core(self, *args, **kwargs):
        context = self.get_context_data(success_message=kwargs.get('success_message'))
        return self.render_to_response(context)

    @staticmethod
    def view_name():
        return 'column_list'

    def get_context_data(self, **kwargs):
        daos.TableCreationDAO(self.object, self.request.user)  # for access validation
        self.table_reservation_dao = daos.TableReservationDAO(self.object, self.request.user)
        context = super().get_context_data(**kwargs)
        column_html = model_html.ColumnUpdateHtml(self.table_reservation_dao, previous_values=self.submitted_values)
        context['column_html_table'] = column_html.as_html_table()
        context['can_see_table_list'] = True
        context.update(self.table_options())
        return context

    def get_queryset(self):
        return models.Column.objects.filter(table=self.table,
                                            table__tablepermission__user=self.request.user,
                                            table__is_hidden=False)

    def post_core(self, *args, **kwargs):
        table_creation_dao = daos.TableCreationDAO(self.object, self.request.user)
        table_creation_dao.rename_columns_and_values(self.request.POST)
        kwargs['success_message'] = f'Column names and values have been updated.'
        return self.get(self.request, *args, **kwargs)

    def post_error(self, error):
        self.submitted_values = self.request.POST
        context = self.get_context_data(error=error)
        return self.render_to_response(context)


class TableAppendForm(forms.Form):
    csv = forms.FileField()
    table_appender = None

    def __init__(self, table_creation_dao, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_creation_dao = table_creation_dao

    def validate_csv(self):
        try:
            table_creation.validate_table_data(self.table_appender.csv_file,
                                               self.table_creation_dao.site_id_column_name())
        except (ValueError, KeyError) as e:
            self.add_error('csv', f'File read error: {e}')

    def initialize_table_appender(self):
        try:
            self.table_appender.calculate_column_value_options()
        except (ValueError, KeyError) as e:
            self.add_error('csv', f'File read error: {e}')

    def is_valid(self):
        if not super().is_valid():
            return False
        self.table_appender = table_creation.CSVTableAppender(self.cleaned_data['csv'], self.table_creation_dao)
        if not self.errors:
            self.validate_csv()
        if not self.errors:
            self.initialize_table_appender()
        return not self.errors

    def append_to_table(self):
        return self.table_appender.append_to_table()


class TableAppendView(TableViewMixin, DetailView):
    template_name_suffix = '_append'

    def __init__(self):
        super().__init__()
        self.submitted_values = None
        self.form = None

    def get_core(self, *args, **kwargs):
        context = self.get_context_data()
        return self.render_to_response(context)

    @staticmethod
    def view_name():
        return 'table_append'

    def get_context_data(self, **kwargs):
        table_creation_dao = daos.TableCreationDAO(self.object, self.request.user)
        if not table_creation_dao.has_site_id_column():
            raise Http404
        context = super().get_context_data(**kwargs)
        if 'form' not in context:
            context['form'] = TableAppendForm(table_creation_dao)
        context.update(self.table_options())
        return context

    def post_core(self, *args, **kwargs):
        table_creation_dao = daos.TableCreationDAO(self.object, self.request.user)
        self.form = TableAppendForm(table_creation_dao, data=self.request.POST, files=self.request.FILES)
        if self.form.is_valid():
            table_creation_dao = self.form.append_to_table()
            return HttpResponseRedirect(reverse('table_detail', args=table_creation_dao.table_detail_args()))
        return self.render_to_response(self.get_context_data(form=self.form))

    def post_error(self, error):
        kwargs = {'error': error}
        if self.form:
            kwargs['form'] = self.form
        return self.render_to_response(self.get_context_data(**kwargs))
