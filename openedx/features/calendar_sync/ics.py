""" Generate .ics files from a user schedule """

from datetime import datetime, timedelta
from urllib.parse import urljoin

from completion.models import BlockCompletion
from django.conf import settings
from django.urls import reverse
from edx_when.api import get_dates_for_course
from icalendar import Calendar, Event, vCalAddress, vText

from openedx.core.djangoapps.site_configuration.helpers import get_site_for_org, get_value
from xmodule.modulestore.django import modulestore

from . import get_calendar_event_id

# icalendar library: https://icalendar.readthedocs.io/en/latest/
# ics format spec: https://tools.ietf.org/html/rfc2445
# ics conventions spec: https://tools.ietf.org/html/rfc5546


def generate_ics_for_event(uid, summary, url, now, start, organizer):
    event = Event()
    event.add('uid', uid)
    event.add('dtstamp', now)
    event.add('organizer', 'CN={}'.format(organizer))
    event.add('summary', summary)
    event.add('dtstart', start)
    event.add('duration', timedelta(0))
    event.add('description', '<a href="{url}">{url}</a>'.format(url=url))

    cal = Calendar()
    cal.add('prodid', '-//Open edX//calendar_sync//EN')
    cal.add('version', '2.0')
    cal.add('method', 'REQUEST')
    cal.add_component(event)

    return cal.to_ical()


def generate_ics_for_user_course(user, course_key):
    """
    Returns an ics-formatted bytestring for a given user and course.

    To pretty-print the bytestring, do: `ics.decode('utf8').replace('\r\n', '\n')`
    """
    completions = BlockCompletion.get_learning_context_completions(user, course_key)
    dates = get_dates_for_course(course_key, user=user)
    platform_name = get_value('platform_name', settings.PLATFORM_NAME)
    site = get_site_for_org(course_key.org)
    store = modulestore()
    now = datetime.utcnow()
    calendars = []

    print('MIKE: site', site, type(site))

    # TODO: replace portions / steal logic from get_course_assignment_due_dates ?

    for ((block_key, field), block_datetime) in dates.items():
        if field == 'due':
            store_data = store.get_item(block_key)
            if not store_data:
                continue

            completion = completions.get(block_key, 0)

            ics = generate_ics_for_event(
                now=now,
                organizer=platform_name,
                start=block_datetime,
                summary=store_data.display_name,
                uid=get_calendar_event_id(user, str(block_key), field, site.domain),
                url=urljoin('https://' + site.domain, reverse('jump_to', args=[course_key, block_key])),
            )
            calendars.append(ics)
        else:
            print('MIKE:', block_key, field, block_datetime)
            continue

    return calendars
