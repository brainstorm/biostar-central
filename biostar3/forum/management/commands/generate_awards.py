from __future__ import absolute_import, division, print_function, unicode_literals
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from optparse import make_option
import os, logging, glob, json
import html2text
from biostar3.forum.models import Post
from biostar3.forum.html import sanitize
import time

"""
Saves html to markdown format.
"""

logger = logging.getLogger('biostar')
from biostar3.forum import awards, models

def abspath(*args):
    "Generates absolute paths."
    return os.path.abspath(os.path.join(*args))


class Command(BaseCommand):
    help = '''Parse html content into markdown.'''

    option_list = BaseCommand.option_list + (
        make_option('--all', action='store_true', default=False,
                    help='generate all awards'),
    )

    def handle(self, *args, **options):

        if options['all']:

            #models.Award.objects.all().delete()
            #models.MessageBody.objects.all().delete()

            for award in awards.get_awards():
                start = time.time()
                award.check()
                end = time.time()
                at = int(end - start)
                ac = models.Award.objects.filter(badge__uuid=award.uuid).count()
                logger.info("processed %s of the %s awards in %d seconds" % (ac, award.uuid, at))