"""
sentry_twilio
~~~~~~~~~~~~~

:copyright: (c) 2012 by Matt Robenolt.
:license: BSD, see LICENSE for more details.
"""

try:
    VERSION = __import__('pkg_resources') \
        .get_distribution('sentry-twilio').version
except Exception as e:
    VERSION = 'unknown'
