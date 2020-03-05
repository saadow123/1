"""
Shareable utilities for third party auth api functions
"""

from social_django.models import UserSocialAuth


def filter_user_social_auth_queryset_by_provider(query_set, provider):
    """
    Filter a query set by the given TPA provider

    Params:
        query_set: QuerySet[UserSocialAuth]
        provider: common.djangoapps.third_party_auth.models.ProviderConfig
    Returns:
        QuerySet[UserSocialAuth]
    """
    query_set = query_set.filter(provider=provider.backend_name)


    # build our query filters
    # When using multi-IdP backend, we only retrieve the ones that are for current IdP.
    # test if the current provider has a slug
    uid = provider.get_social_auth_uid('uid')
    if uid != 'uid':
        # if yes, we add a filter for the slug on uid column
        query_set = query_set.filter(uid__startswith=uid[:-3])

    return query_set
