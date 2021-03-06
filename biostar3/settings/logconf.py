# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.


class LogRateLimit(object):
    """
    A log filter that limits the number of emails that are sent to admins.
    """
    TIMEOUT = 600
    CACHE_KEY = "lograte-limiter"

    def filter(self, record):
        from django.core.cache import cache
        exists = cache.get(self.CACHE_KEY)
        if not exists:
            cache.set(self.CACHE_KEY, 1, self.TIMEOUT)
        return not exists

LOGGING = {
    'version': 1,

    'disable_existing_loggers': False,

    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s.%(funcName)s %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },

    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        },

        'ratelimit': {
            '()': 'biostar3.settings.logconf.LogRateLimit',
        }
    },

    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false', 'ratelimit'],
            'class': 'django.utils.log.AdminEmailHandler'
        },

        'console':{
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },

        'simple':{
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
    },

    'loggers': {

        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },

        'biostar':{
            'level': 'INFO',
            'handlers': ['console'],
        },

        'command':{
            'level': 'INFO',
            'handlers': ['console'],
        },

       'simple-logger':{
            'level': 'INFO',
            'handlers': ['simple'],
        },
    }

}

