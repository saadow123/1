""" Tests for the Calendar Sync models """

from datetime import datetime, timedelta

import ddt
import waffle
from django.contrib.messages.middleware import MessageMiddleware
from django.test import RequestFactory
from django.urls import reverse
from freezegun import freeze_time
from mock import patch
from pytz import utc

from course_modes.models import CourseMode
from course_modes.tests.factories import CourseModeFactory
from lms.djangoapps.courseware.courses import get_course_date_blocks
from lms.djangoapps.courseware.date_summary import (
    CertificateAvailableDate,
    CourseAssignmentDate,
    CourseEndDate,
    CourseExpiredDate,
    CourseStartDate,
    TodaysDate,
    VerificationDeadlineDate,
    VerifiedUpgradeDeadlineDate
)
from lms.djangoapps.courseware.models import (
    CourseDynamicUpgradeDeadlineConfiguration,
    DynamicUpgradeDeadlineConfiguration,
    OrgDynamicUpgradeDeadlineConfiguration
)
from lms.djangoapps.commerce.models import CommerceConfiguration
from lms.djangoapps.verify_student.models import VerificationDeadline
from lms.djangoapps.verify_student.tests.factories import SoftwareSecurePhotoVerificationFactory
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.schedules.signals import CREATE_SCHEDULE_WAFFLE_FLAG
from openedx.core.djangoapps.self_paced.models import SelfPacedConfiguration
from openedx.core.djangoapps.site_configuration.tests.factories import SiteFactory
from openedx.core.djangoapps.user_api.preferences.api import set_user_preference
from openedx.core.djangoapps.waffle_utils.testutils import override_waffle_flag
from openedx.features.course_duration_limits.models import CourseDurationLimitConfig
from openedx.features.course_experience import (
    DATE_WIDGET_V2_FLAG, UNIFIED_COURSE_TAB_FLAG, UPGRADE_DEADLINE_MESSAGE, CourseHomeMessages
)
from student.tests.factories import TEST_PASSWORD, CourseEnrollmentFactory, UserFactory
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory


from ..ics import generate_ics_for_user_course


def create_user(verification_status=None):
    """ Create a new User instance.

    Arguments:
        verification_status (str): User's verification status. If this value is set an instance of
            SoftwareSecurePhotoVerification will be created for the user with the specified status.
    """
    user = UserFactory()

    if verification_status is not None:
        SoftwareSecurePhotoVerificationFactory.create(user=user, status=verification_status)

    return user


def create_course_run(
    days_till_start=1, days_till_end=14, days_till_upgrade_deadline=4, days_till_verification_deadline=14,
):
    """ Create a new course run and course modes.

    All date-related arguments are relative to the current date-time (now) unless otherwise specified.

    Both audit and verified `CourseMode` objects will be created for the course run.

    Arguments:
        days_till_end (int): Number of days until the course ends.
        days_till_start (int): Number of days until the course starts.
        days_till_upgrade_deadline (int): Number of days until the course run's upgrade deadline.
        days_till_verification_deadline (int): Number of days until the course run's verification deadline. If this
            value is set to `None` no deadline will be verification deadline will be created.
    """
    now = datetime.now(utc)
    course = CourseFactory.create(start=now + timedelta(days=days_till_start))

    course.end = None
    if days_till_end is not None:
        course.end = now + timedelta(days=days_till_end)

    CourseModeFactory(course_id=course.id, mode_slug=CourseMode.AUDIT)
    CourseModeFactory(
        course_id=course.id,
        mode_slug=CourseMode.VERIFIED,
        expiration_datetime=now + timedelta(days=days_till_upgrade_deadline)
    )

    if days_till_verification_deadline is not None:
        VerificationDeadline.objects.create(
            course_key=course.id,
            deadline=now + timedelta(days=days_till_verification_deadline)
        )

    return course


class TestIcsGeneration(SharedModuleStoreTestCase):
    """ Tests """
    @classmethod
    def setUpClass(cls):
        """ Set up any course data """
        super().setUpClass()
        cls.course = CourseFactory.create()
        cls.course_key = cls.course.id

    def setUp(self):
        super().setUp()
        self.user = UserFactory()

    def test_generate_ics_for_user_course(self):
        expected = '''BEGIN:VCALENDAR
VERSION:1.0
PRODID:-//Open edX//calendar_sync//
END:VCALENDAR
BEGIN:VTODO
DUE;TZID=UTC;VALUE=DATE-TIME:20200218T183927Z
SUMMARY:Python meeting about calendaring
END:VTODO
'''

        course = create_course_run(days_till_start=-100)
        user = create_user()
        request = RequestFactory().request()
        request.user = user
        CourseEnrollmentFactory(course_id=course.id, user=user, mode=CourseMode.VERIFIED)
        now = datetime.now(utc)
        assignment_title_html = ['<a href=', '</a>']
        with self.store.bulk_operations(course.id):
            section = ItemFactory.create(category='chapter', parent_location=course.location)
            subsection_1 = ItemFactory.create(
                category='sequential',
                display_name='Released',
                parent_location=section.location,
                start=now - timedelta(days=1),
                due=now + timedelta(days=6),
                graded=True,
            )
            subsection_2 = ItemFactory.create(
                category='sequential',
                display_name='Not released',
                parent_location=section.location,
                start=now + timedelta(days=1),
                due=now + timedelta(days=7),
                graded=True,
            )
            subsection_3 = ItemFactory.create(
                category='sequential',
                display_name='Third nearest assignment',
                parent_location=section.location,
                start=now + timedelta(days=1),
                due=now + timedelta(days=8),
                graded=True,
            )
            subsection_4 = ItemFactory.create(
                category='sequential',
                display_name='Past due date',
                parent_location=section.location,
                start=now - timedelta(days=14),
                due=now - timedelta(days=7),
                graded=True,
            )
            subsection_5 = ItemFactory.create(
                category='sequential',
                display_name='Not returned since we do not get non-graded subsections',
                parent_location=section.location,
                start=now + timedelta(days=1),
                due=now - timedelta(days=7),
                graded=False,
            )
            subsection_6 = ItemFactory.create(
                category='sequential',
                display_name='No start date',
                parent_location=section.location,
                start=None,
                due=now + timedelta(days=9),
                graded=True,
            )
            subsection_7 = ItemFactory.create(
                category='sequential',
                # Setting display name to None should set the assignment title to 'Assignment'
                display_name=None,
                parent_location=section.location,
                start=now - timedelta(days=14),
                due=now + timedelta(days=10),
                graded=True,
            )

        with patch('openedx.features.calendar_sync.ics.get_dates_for_course') as mock_get_dates:
            mock_get_dates.return_value = {
                (subsection_1.location, 'due'): subsection_1.due,
                (subsection_1.location, 'start'): subsection_1.start,
                (subsection_2.location, 'due'): subsection_2.due,
                (subsection_2.location, 'start'): subsection_2.start,
                (subsection_3.location, 'due'): subsection_3.due,
                (subsection_3.location, 'start'): subsection_3.start,
                (subsection_4.location, 'due'): subsection_4.due,
                (subsection_4.location, 'start'): subsection_4.start,
                (subsection_5.location, 'due'): subsection_5.due,
                (subsection_5.location, 'start'): subsection_5.start,
                (subsection_6.location, 'due'): subsection_6.due,
                (subsection_7.location, 'due'): subsection_7.due,
                (subsection_7.location, 'start'): subsection_7.start,
            }
            generated = generate_ics_for_user_course(self.user, self.course_key)

        for (i, g) in enumerate(generated):
            print(g.decode('utf8').replace('\r\n', '\n'), file=open('mike%d.ics' % i, 'w'))
        self.assertEqual(generated.decode('utf8').replace('\r\n', '\n'), expected)
        assert False
