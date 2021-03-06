from django.apps import AppConfig
from django.db.models.signals import post_migrate
from biostar3.forum import models, awards
from biostar3.forum.models import User, Post, PostSub
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.contrib.sites.models import Site
from django.db import transaction
from django.db.models import Q, F
from django.contrib.staticfiles import finders
from django.core.files.base import File
import html2text

import logging

logger = logging.getLogger('biostar')


class BiostarAppConfig(AppConfig):
    name = 'biostar3.forum'
    verbose_name = 'Biostar Forum'

    def ready(self):
        """
        Triggers when the application configuration is ready.
        """
        # This registers the signals
        from . import signals

        # Register the extra signals
        signals.register()

        # Add the post migration signal.
        post_migrate.connect(post_migrate_tasks, sender=self)

    @property
    def app_label(self):
        return self.name.split(".")[-1]

def post_migrate_tasks(sender, **kwargs):
    """
    Sets up minimally required site content post migration.
    """

    # Set up the default domain.
    site = Site.objects.get_current()
    if site.domain != settings.SITE_DOMAIN:
        site.name = settings.SITE_NAME
        site.domain = settings.SITE_DOMAIN
        site.save()
        logger.info("Adding site=%s, name=%s, domain=%s." % (site.id, site.name, site.domain))

    # Create moderator sites.
    Site.objects.get_or_create(domain=settings.MODERATORS_SITE_DOMAIN, name=settings.MODERATOR_SITE_NAME)

    # Needs ADMINS settings.
    if not settings.ADMINS:
        raise ImproperlyConfigured("settings must include ADMINS attribute.")

    # Check that the default logo exists.
    default_logo = finders.find(settings.DEFAULT_GROUP_LOGO)
    if not default_logo:
        raise ImproperlyConfigured("Cannot find default group logo at %s." % settings.DEFAULT_GROUP_LOGO)

    # Create the admin users if necessary.
    for name, email in settings.ADMINS:
        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.create(
                email=email, name=name, type=User.ADMIN,
                is_staff=True, is_admin=True, is_superuser=True)
            user.set_password(settings.SECRET_KEY)
            user.save()
            logger.info("Added admin user with email=%s, password=SECRET_KEY, name=%s." % (user.email, user.name))

    # Get the first admin on the list.
    admin = User.objects.get(email=settings.ADMINS[0][1])

    # Initialize the awards.
    awards.get_awards()