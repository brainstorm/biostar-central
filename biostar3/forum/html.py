"""
Handles the output formatting and conversions
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import bleach, re, logging, requests
from django.conf import settings
from markdown2 import markdown
from html5lib.tokenizer import HTMLTokenizer

logger = logging.getLogger('biostar')

# Tags that are allowed by default
ALLOWED_TAGS = bleach.ALLOWED_TAGS + settings.ALLOWED_TAGS
ALLOWED_STYLES = bleach.ALLOWED_STYLES + settings.ALLOWED_STYLES
ALLOWED_ATTRIBUTES = dict(bleach.ALLOWED_ATTRIBUTES)
ALLOWED_ATTRIBUTES.update(settings.ALLOWED_ATTRIBUTES)

# Moderators may use more tags and styles
TRUSTED_TAGS = ALLOWED_TAGS + settings.TRUSTED_TAGS
TRUSTED_STYLES = ALLOWED_STYLES + settings.TRUSTED_STYLES
TRUSTED_ATTRIBUTES = dict(ALLOWED_ATTRIBUTES)
TRUSTED_ATTRIBUTES.update(settings.TRUSTED_ATTRIBUTES)

# Patterns that will be recognized and embedded into the posts as links.
USER_PATTERN = r"http(s)?://%s/u/(?P<uid>(\d+))(/)?" % settings.SITE_DOMAIN
POST_PATTERN1 = r"http(s)?://%s/p/(?P<uid>(\d+))(/)?" % settings.SITE_DOMAIN
POST_PATTERN2 = r"http(s)?://%s/p/\d+/\#(?P<uid>(\d+))(/)?" % settings.SITE_DOMAIN
HANDLE_PATTERN = r"(?P<start>(^|\s|\())@(?P<uid>(\w+))"

# Matches gists that may be embeded.
GIST_PATTERN = r"https://gist.github.com/(?P<uid>([\w/]+))"

# Youtube can be embedded with different patterns
YOUTUBE_PATTERN1 = r"http(s)?://www.youtube.com/watch\?v=(?P<uid>([-_\w]+))(/)?"
YOUTUBE_PATTERN2 = r"http(s)?://www.youtube.com/embed/(?P<uid>([-_\w]+))(/)?"
YOUTUBE_PATTERN3 = r"http(s)?://youtu.be/(?P<uid>([-_\w]+))(/)?"

# Twitter: tweets to embed.
TWITTER_PATTERN = r"http(s)?://twitter.com/\w+/status(es)?/(?P<uid>([\d]+))"

YOUTUBE_HTML = '<iframe width="420" height="315" src="//www.youtube.com/embed/{}" frameborder="0" allowfullscreen></iframe>'
def get_embedded_youtube(patt):
    uid = patt.group("uid")
    return YOUTUBE_HTML.format(uid)

GIST_HTML = '<script src="https://gist.github.com/{}.js"></script>'
def get_embedded_gist(patt):
    uid = patt.group("uid")
    return GIST_HTML.format(uid)


def highlight_handle(patt):
    uid = patt.group("uid")
    return ' @<b>{}</b>'.format(uid)


def get_embedded_tweet(patt):
    """
    Get the HTML code with the embedded tweet.
    It requires an API call at https://api.twitter.com/1/statuses/oembed.json as documented here:
    https://dev.twitter.com/docs/embedded-tweets - section "Embedded Tweets for Developers"
    https://dev.twitter.com/docs/api/1/get/statuses/oembed

    Params:
    tweet_id -- a tweet's numeric id like 2311234267 for the tweet at
    https://twitter.com/Linux/status/2311234267
    """
    tweet_id = patt.group("tweet_id")
    try:
        response = requests.get("https://api.twitter.com/1/statuses/oembed.json?id={}".format(
            tweet_id))
        return response.json()['html']
    except:
        return ''

# Compile the patterns into regular expressions.
USER_RE = re.compile(USER_PATTERN)
POST_RE1 = re.compile(POST_PATTERN1)
POST_RE2 = re.compile(POST_PATTERN2)
GIST_RE = re.compile(GIST_PATTERN, re.MULTILINE | re.IGNORECASE)
YOUTUBE_RE1 = re.compile(YOUTUBE_PATTERN1, re.MULTILINE | re.IGNORECASE)
YOUTUBE_RE2 = re.compile(YOUTUBE_PATTERN2, re.MULTILINE | re.IGNORECASE)
YOUTUBE_RE3 = re.compile(YOUTUBE_PATTERN3, re.MULTILINE | re.IGNORECASE)
TWITTER_RE = re.compile(TWITTER_PATTERN, re.MULTILINE | re.IGNORECASE)
HANDLE_RE = re.compile(HANDLE_PATTERN)


def strip_tags(text):
    "Strip html tags from text"
    result = bleach.clean(text, tags=[], attributes=[], styles={}, strip=True)
    return result


def clean(text):
    "Sanitize text with no other substitutions"
    result = bleach.clean(text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, styles=ALLOWED_STYLES)
    return result


def sanitize(text, user, safe=False):
    "Sanitize text and expand links to match content"

    if not text.strip():
        # No content there.
        return ""

    # Avoid circular imports.
    from biostar3.forum.models import User, Post

    def internal_links(attrs, new=False):
        """Creates links to internal content"""
        try:

            # Don't resolve the link if a user has already specified a text for it.
            href, _text = attrs['href'], attrs['_text']

            if href != _text:
                return attrs

            # Find and match post URL patterns
            post_patt = POST_RE1.search(href) or POST_RE2.search(href)
            if post_patt:
                uid = post_patt.group("uid")
                attrs['_text'] = Post.objects.get(id=uid).title

            # Find an match user URL patterns.
            user_patt = USER_RE.search(href)
            if user_patt:
                uid = user_patt.group("uid")
                attrs['_text'] = User.objects.get(id=uid).name



        except Exception as exc:
            # This function is a convenience feature.
            # Let's not let it crash the whole post parsing.
            logger.error(exc)

        return attrs

    def require_protocol(attrs, new=False):
        "Linkify only if protocols are present"

        if new:
            href, _text = attrs['href'], attrs['_text']
            if href != _text:
                # This has already been linkified.
                return attrs

            # Don't linkify links with no protocols.
            if href[:4] not in ('http', 'ftp:'):
                return None

        return attrs

    # The functions that will be applied when linkifying
    callbacks = [internal_links, require_protocol]

    # Staff may use more dangerous HTML objects.
    if user and user.is_staff:
        tags, attrs, styles = TRUSTED_TAGS, TRUSTED_ATTRIBUTES, TRUSTED_STYLES
    else:
        tags, attrs, styles = ALLOWED_TAGS, ALLOWED_ATTRIBUTES, ALLOWED_STYLES

    # First sanitize the text.

    try:
        # Apply the markdown transformation.
        # We'll protect against library crashes by a generic Exception catch.
        html = markdown(text, extras=["fenced-code-blocks", "code-friendly", "nofollow", "spoiler"])
    except Exception as exc:
        logger.error('crash during markdown conversion: %s' % exc)
        html = text

    if not safe:
        html = bleach.clean(html, tags=tags, attributes=attrs, styles=styles)

    # Now embed the links.
    html = embed_links(html)

    try:
        # Turn links into urls. We had bleach.linkify crash very rarely so we'll trap that.
        # We use a more lenient tokenizer since the content is already cleaned.
        html = bleach.linkify(html, callbacks=callbacks, skip_pre=True, tokenizer=HTMLTokenizer)
    except Exception as exc:
        logger.error('crash during bleach linkify: %s' % exc)
        html = html

    # Strip whitespace.
    html = html.strip()

    return html


def find_tagged_names(post):
    """
    Returns the users mentioned in a post by handle.
    """
    tags = [patt.group("uid") for patt in HANDLE_RE.finditer(post.content)]
    return tags

def embed_links(text):
    targets = [
        (GIST_RE, get_embedded_gist),
        (YOUTUBE_RE1, get_embedded_youtube),
        (YOUTUBE_RE2, get_embedded_youtube),
        (YOUTUBE_RE3, get_embedded_youtube),
        (TWITTER_RE, get_embedded_tweet),
        (HANDLE_RE, highlight_handle),
    ]

    for regex, func in targets:
        patt = regex.search(text)
        if patt:

            new_value = func(patt)
            text = regex.sub(new_value, text)

    return text

