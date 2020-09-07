from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db.transaction import atomic
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy, gettext
from django.views.generic import ListView
from django.views.generic.edit import FormView
from . import model_html
from . import models
from datastore import daos


class SignupForm(UserCreationForm):
    email = forms.EmailField(label=gettext_lazy('Email'), required=True,
                             help_text=gettext_lazy('SignupFormEmailHelpText'))
    activation_code = forms.CharField(label=gettext_lazy('ActivationCode'), required=True,
                                      help_text=gettext_lazy('SignupFormActivationCodeHelpText'))

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def is_valid(self):
        if not super().is_valid():
            return False
        activation_code = self.cleaned_data['activation_code']
        try:
            models.ActivationCode.objects.get(code=activation_code)
            return True
        except models.ActivationCode.DoesNotExist:
            self.add_error('activation_code', gettext('ActivationCodeDoesNotExist').format(activation_code))
            return False

    @atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_active = False
        if commit:
            user.save()
            daos.register_user_for_table(self.request, user, self.cleaned_data['activation_code'])
        return user


class SignupView(FormView):
    template_name = 'signup.html'
    success_url = '/signup-thanks/'
    form_class = SignupForm

    def form_valid(self, form):
        form.request = self.request
        form.save()
        return super().form_valid(form)

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return HttpResponseRedirect(reverse('table_list'))
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return HttpResponseRedirect(reverse('table_list'))
        return super().post(request, *args, **kwargs)


class StudyAccessForm(forms.Form):
    activation_code = forms.CharField(label=gettext_lazy('ActivationCode'), required=True,
                                      help_text=gettext_lazy('SignupFormActivationCodeHelpText'))

    def is_valid(self):
        if not super().is_valid():
            return False
        activation_code = self.cleaned_data['activation_code']
        try:
            models.ActivationCode.objects.get(code=activation_code)
            return True
        except models.ActivationCode.DoesNotExist:
            self.add_error('activation_code', gettext('ActivationCodeDoesNotExist').format(activation_code))
            return False

    def save(self, commit=True):
        if commit:
            daos.register_user_for_table(self.request, self.user, self.cleaned_data['activation_code'])


class StudyAccessView(FormView):
    template_name = 'study-access.html'
    success_url = '/study-access-thanks/'
    form_class = StudyAccessForm

    def form_valid(self, form):
        form.request = self.request
        form.user = self.request.user
        form.save()
        return super().form_valid(form)


class AccessApproval(ListView):
    model = models.TableSiteIdAccess

    def get(self, request, *args, **kwargs):
        self.request = request
        self.object_list = self.get_queryset()
        context = self.get_context_data(user_can_create_tables=True, **kwargs)
        context['html_table'] = model_html.TableSiteIdAccessHtml(self.object_list).as_html_table()
        return self.render_to_response(context)

    @atomic
    def post(self, request, *args, **kwargs):
        self.request = request
        try:
            pk = self._extract_row_pk()
            table_site_id_access_dao = daos.TableSiteAccessDAO(request.user)
            user, table_name = table_site_id_access_dao.approve(pk)
            kwargs['success_message'] = f'`{user}` has been granted access to table `{table_name}`.'
        except Exception as error:
            kwargs['error'] = error
        return self.get(request, *args, **kwargs)

    def get_queryset(self):
        table_site_id_access_dao = daos.TableSiteAccessDAO(self.request.user)
        return table_site_id_access_dao.get_inactive_queryset()

    def _extract_row_pk(self):
        for key in self.request.POST:
            if key.startswith('site_'):
                if self.request.POST[key] != 'Approve':
                    raise ValueError('Did not find approval event in request')
                return key.replace('site_', '')
        raise ValueError('Did not find row key in request')
