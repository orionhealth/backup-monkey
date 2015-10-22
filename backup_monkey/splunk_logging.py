import logging

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class SplunkLogging(object):

    __metaclass__ = Singleton

    log_file = '/var/log/backup_monkey.log'
    app = 'BACKUP_MONKEY'
    keys = ['app', 'body', 'severity', 'src_account', 'src_role', 'src_region', 'src_volume', 'src_snapshot', 'src_tags', 'subject', 'type', 'category']
    logger = logging.getLogger(__name__)
    formatter = logging.Formatter('%(asctime)s %(message)s', '%Y-%m-%d %H:%M:%S')

    handler = logging.FileHandler(log_file)
    logger.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    @classmethod
    def set_path(cls, path):
        cls.handler = logging.FileHandler(path)
        cls.handler.setFormatter(cls.formatter)
        for h in cls.logger.handlers:
            cls.logger.removeHandler(h)
        cls.logger.addHandler(cls.handler)

    @classmethod
    def reset_path(cls):
        cls.set_path(cls.log_file)

    @classmethod
    def set_app(cls, app):
        cls.app = app

    @classmethod
    def write(cls, **kwargs):
      """ Write to log file which will be parsed by splunk.
      severity is one of: critical, high, medium, low, informational, unknown
      type is one of: alarm, alert, event, task, unknown
      """
      for k in cls.keys:
        if k not in kwargs:
          kwargs[k] = ''
      kwargs['app'] = kwargs['app'] if kwargs['app'] else cls.app
      kwargs['severity'] = kwargs['severity'] if kwargs['severity'] in ['critical', 'high', 'medium', 'low', 'informational'] else 'unknown' 
      kwargs['type'] = kwargs['type'] if kwargs['type'] in ['alarm', 'alert', 'event', 'task'] else 'unknown' 
      cls.logger.debug(','.join(sorted(['%s=%s' % (k, kwargs[k].replace('\r', ' ').replace('\n', ' ').strip()) for k in cls.keys if k in kwargs])))
