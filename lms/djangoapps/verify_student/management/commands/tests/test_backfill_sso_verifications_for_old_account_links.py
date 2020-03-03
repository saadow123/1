"""
Tests for management command backfill_sso_verifications_for_old_account_links
"""

from django.core.management import call_command
from django.core.management.base import CommandError

from lms.djangoapps.program_enrollments.management.commands.tests.utils import UserSocialAuthFactory
from lms.djangoapps.verify_student.models import SSOVerification
from third_party_auth.tests.testutil import TestCase


class TestBackfillSSOVerificationsCommand(TestCase):
    """
    Tests for management command for backfilling SSO verification records
    """
    slug = 'test'

    def setUp(self):
        super(TestBackfillSSOVerificationsCommand, self).setUp()
        self.enable_saml()
        self.provider = self.configure_saml_provider(
            name="Test",
            slug=self.slug,
            enabled=True,
            enable_sso_id_verification=True,
        )
        self.user_social_auth1 = UserSocialAuthFactory(slug=self.slug)
        self.user1 = self.user_social_auth1.user

    def test_fails_without_required_param(self):
        with self.assertRaises(CommandError):
            call_command('backfill_sso_verifications_for_old_account_links')

    def test_fails_without_named_provider_config(self):
        with self.assertRaises(CommandError):
            call_command('backfill_sso_verifications_for_old_account_links', '--provider-slug', 'gatech')

    def test_existing_provider(self):
        call_command('backfill_sso_verifications_for_old_account_links', '--provider-slug', self.provider.provider_id)
       
    def test_sso_updated(self):
        self.assertTrue(SSOVerification.objects.count() == 0)
        call_command('backfill_sso_verifications_for_old_account_links', '--provider-slug', self.provider.provider_id)
        self.assertTrue(SSOVerification.objects.count() > 0)

