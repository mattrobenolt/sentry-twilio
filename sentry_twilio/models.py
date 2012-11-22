"""
sentry_twilio.models
~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2012 by Matt Robenolt.
:license: BSD, see LICENSE for more details.
"""

import re
import urllib
import urllib2
from django import forms
from django.utils.translation import ugettext_lazy as _
from sentry.plugins.bases.notify import NotificationPlugin

import sentry_twilio

phone_re = re.compile(r'^(\+1)?\d{10}$')  # US only :(
split_re = re.compile(r'\s*,\s*|\s+')

twilio_sms_endpoint = 'https://api.twilio.com/2010-04-01/Accounts/{0}/SMS/Messages.json'


class TwilioConfigurationForm(forms.Form):
    account_sid = forms.CharField(label=_('Account SID'), required=True,
        widget=forms.TextInput(attrs={'class': 'span6'}))
    auth_token = forms.CharField(label=_('Auth Token'), required=True,
        widget=forms.PasswordInput(render_value=True, attrs={'class': 'span6'}))
    sms_from = forms.CharField(label=_('SMS From #'), required=True,
        help_text=_('Digits only'),
        widget=forms.TextInput(attrs={'placeholder': 'e.g. 3305093095'}))
    sms_to = forms.CharField(label=_('SMS To #s'), required=True,
        help_text=_('Recipient(s) phone numbers separated by commas or lines'),
        widget=forms.Textarea(attrs={'placeholder': 'e.g. 3305093095, 5555555555'}))

    def clean_sms_from(self):
        data = self.cleaned_data['sms_from']
        if not phone_re.match(data):
            raise forms.ValidationError('{0} is not a valid phone number.'.format(data))
        if not data.startswith('+1'):
            # Append the +1 when saving
            data = '+1' + data
        return data

    def clean_sms_to(self):
        data = self.cleaned_data['sms_to']
        phones = set(filter(bool, split_re.split(data)))
        for phone in phones:
            if not phone_re.match(phone):
                raise forms.ValidationError('{0} is not a valid phone number.'.format(phone))

        # Add a +1 to all numbers if they don't have it
        phones = map(lambda x: x if x.startswith('+1') else '+1' + x, phones)
        return ','.join(phones)

    def clean(self):
        # TODO: Ping Twilio and check credentials (?)
        return self.cleaned_data


class TwilioPlugin(NotificationPlugin):
    author = 'Matt Robenolt'
    author_url = 'https://github.com/mattrobenolt'
    version = sentry_twilio.VERSION
    description = 'A plugin for Sentry which sends SMS notifications via Twilio'
    resource_links = (
        ('Documentation', 'https://github.com/mattrobenolt/sentry-twilio/blob/master/README.md'),
        ('Bug Tracker', 'https://github.com/mattrobenolt/sentry-twilio/issues'),
        ('Source', 'https://github.com/mattrobenolt/sentry-twilio'),
        ('Twilio', 'http://www.twilio.com/'),
    )

    slug = 'twilio'
    title = _('Twilio (SMS)')
    conf_title = title
    conf_key = 'twilio'
    project_conf_form = TwilioConfigurationForm

    def is_configured(self, request, project, **kwargs):
        return all([self.get_option(o, project) for o in ('account_sid', 'auth_token', 'sms_from', 'sms_to')])

    def get_send_to(self, *args, **kwargs):
        # This doesn't depend on email permission... stuff.
        return True

    def notify_users(self, group, event):
        project = group.project

        body = 'Sentry [{0}] {1}: {2}'.format(
            project.name.encode('utf-8'),
            event.get_level_display().upper().encode('utf-8'),
            event.error().encode('utf-8').splitlines()[0]
        )
        body = body[:160]  # Truncate to 160 characters

        account_sid = self.get_option('account_sid', project)
        auth_token = self.get_option('auth_token', project)
        sms_from = self.get_option('sms_from', project)
        sms_to = self.get_option('sms_to', project).split(',')
        endpoint = twilio_sms_endpoint.format(account_sid)

        # Herein lies the goat rodeo that is urllib2

        # Sure, totally makes sense. PasswordMgrWithDefault..fuck
        manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        manager.add_password(None, endpoint, account_sid, auth_token)
        # Obviously, you need an AuthHandler thing
        handler = urllib2.HTTPBasicAuthHandler(manager)
        # Build that fucking opener
        opener = urllib2.build_opener(handler)
        # Install that shit, hardcore
        urllib2.install_opener(opener)

        for phone in sms_to:
            data = urllib.urlencode({
                'From': sms_from,
                'To': phone,
                'Body': body,
            })
            try:
                urllib2.urlopen(endpoint, data)
            except urllib2.URLError:
                # This could happen for any number of reasons
                # Twilio may have legitimately errored,
                # Bad auth credentials, etc
                pass
