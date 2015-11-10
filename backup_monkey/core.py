# Copyright 2013 Answers for AWS LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging, sys, os, re

from boto.exception import NoAuthHandlerFound, BotoServerError
from boto import ec2

from exception import BackupMonkeyException

__all__ = ('BackupMonkey', 'Logging')
log = logging.getLogger(__name__)

from splunk_logging import SplunkLogging  
from status import BackupMonkeyStatus as _status

class BackupMonkey(object):

    def __init__(self, region, max_snapshots_per_volume, tags, reverse_tags, cross_account_number, cross_account_role, verbose):
        Logging().configure(verbose)
        self._region = region
        self._prefix = 'BACKUP_MONKEY'
        self._snapshots_per_volume = max_snapshots_per_volume
        self._tags = tags
        self._reverse_tags = reverse_tags
        self._cross_account_number = cross_account_number
        self._cross_account_role = cross_account_role
        self._conn = self.get_connection()

    def _info(self, **kwargs):
        log.info('%s: %s' % (kwargs['subject'], kwargs['body']) if 'subject' in kwargs and 'body' in kwargs else kwargs['subject'] if 'subject' in kwargs else None)
        kwargs['severity'] = kwargs['severity'] if 'severity' in kwargs else 'informational' 
        kwargs['type'] = kwargs['type'] if 'type' in kwargs else 'event' 
        kwargs['src_region'] = self._region
        SplunkLogging.write(**kwargs)

    def get_connection(self):
        ret = None
        if self._cross_account_number and self._cross_account_role:
            self._info(
                subject=_status.parse_status('cross_account_connect', (self._cross_account_number, self._cross_account_role, self._region)), 
                src_account=self._cross_account_number, 
                src_role=self._cross_account_role,
                category='connection')
            from boto.sts import STSConnection
            import boto
            try:
                role_arn = 'arn:aws:iam::%s:role/%s' % (self._cross_account_number, self._cross_account_role)
                sts = STSConnection()
                assumed_role = sts.assume_role(role_arn=role_arn, role_session_name='AssumeRoleSession')
                ret = ec2.connect_to_region(
                    self._region,
                    aws_access_key_id=assumed_role.credentials.access_key, 
                    aws_secret_access_key=assumed_role.credentials.secret_key, 
                    security_token=assumed_role.credentials.session_token
                )
            except BotoServerError, e:
                raise BackupMonkeyException('%s: %s' % (_status.parse_status('cross_account_error'), e.message),
                    subject=_status.parse_status('cross_account_error'),
                    body=e.message,
                    src_account=self._cross_account_number,
                    src_role=self._cross_account_role,
                    category='connection')
        else:
            self._info(
                subject=_status.parse_status('region_connect', self._region), 
                category='connection')
            try:
                ret = ec2.connect_to_region(self._region)
            except NoAuthHandlerFound, e:
                log.critical('No AWS credentials found. To configure Boto, please read: http://boto.readthedocs.org/en/latest/boto_config_tut.html')
                raise BackupMonkeyException('%s: %s' % (_status.parse_status('region_connect_error'), e.message),
                    subject=_status.parse_status('region_connect_error'),
                    body=e.message,
                    category='connection')
        if not ret:
            raise BackupMonkeyException(_status.parse_status('region_connect_invalid', self._region),
                subject=_status.parse_status('region_connect_invalid', self._region),
                category='connection')
        return ret

    def get_filters(self):
        filters = None
        try:
            filters = dict([t.split(':') for t in self._tags])
            for f in filters.keys():
                try:
                    filters[f] = eval(filters[f])
                except Exception:
                    pass
        except ValueError, e:
            raise BackupMonkeyException('%s: %s' % (_status.parse_status('tags_invalid'), str(e)),
                subject=_status.parse_status('tags_invalid'),
                body=str(e),
                src_tags=' '.join(self._tags),
                category='parameters')
        if not self._reverse_tags:
            for f in filters.keys():
                filters['tag:%s' % f] = filters.pop(f)
        return filters

    def get_all_volumes(self, **kwargs):
        try:
            return self._conn.get_all_volumes(**kwargs)
        except BotoServerError, e:
            raise BackupMonkeyException('%s: %s' % (_status.parse_status('volumes_fetch_error', self._region), e.message),
                subject=_status.parse_status('volumes_fetch_error', self._region),
                body=e.message,
                category='volumes')

    def get_volumes_to_snapshot(self):
        ''' Returns volumes to snapshot based on passed in tags '''
        self._info(
            subject=_status.parse_status('volumes_fetch', self._region), 
            category='volumes')
        volumes = [] 
        if self._reverse_tags:
            filters = self.get_filters()
            black_list = []
            for f in filters.keys():
                if isinstance(filters[f], list):
                    black_list = black_list + [(f, i) for i in filters[f]]
                else:
                    black_list.append((f, filters[f]))
            for v in self.get_all_volumes():
                if len(set(v.tags.items()) - set(black_list)) == len(set(v.tags.items())):
                    volumes.append(v) 
            return volumes
        else:
            if self._tags:
                return self.get_all_volumes(filters=self.get_filters())
            else:
                return self.get_all_volumes()
    
    def remove_reserved_tags(self, tags):
        return dict((key,value) for key, value in tags.iteritems() if not key.startswith('aws:'))
        
    def snapshot_volumes(self):
        ''' Loops through all EBS volumes and creates snapshots of them '''

        log.info('Getting list of EBS volumes')
        volumes = self.get_volumes_to_snapshot()
        log.info('Found %d volumes', len(volumes))
        for volume in volumes:            
            description_parts = [self._prefix]
            description_parts.append(volume.id)
            if volume.attach_data.instance_id:
                description_parts.append(volume.attach_data.instance_id)
            if volume.attach_data.device:
                description_parts.append(volume.attach_data.device)
            description = ' '.join(description_parts)
            self._info(subject=_status.parse_status('snapshot_create', (volume.id, description)), 
                src_volume=volume.id,
                src_tags=' '.join([':'.join(i) for i in volume.tags.items()]),
                category='snapshots')
            try:
                snapshot = volume.create_snapshot(description)
                if volume.tags:
                    snapshot.add_tags(self.remove_reserved_tags(volume.tags))
                self._info(subject=_status.parse_status('snapshot_create_success', (snapshot.id, volume.id)), 
                    src_volume=volume.id,
                    src_snapshot=snapshot.id,
                    src_tags=' '.join([':'.join(i) for i in snapshot.tags.items()]),
                    category='snapshots')
            except BotoServerError, e:
                raise BackupMonkeyException('%s: %s' % (_status.parse_status('snapshot_create_error', volume.id), e.message),
                    subject=_status.parse_status('snapshot_create_error', volume.id),
                    body=e.message,
                    src_volume=volume.id,
                    src_tags=' '.join([':'.join(i) for i in volume.tags.items()]),
                    category='volumes')
        return True


    def remove_old_snapshots(self):
        ''' Loop through this account's snapshots, and remove the oldest ones
        where there are more snapshots per volume than required '''
        log.info('Configured to keep %d snapshots per volume', self._snapshots_per_volume)
        self._info(
            subject=_status.parse_status('snapshots_fetch', self._region),
            category='snapshots')
        try:
            snapshots = self._conn.get_all_snapshots(owner='self')
        except BotoServerError, e:
            raise BackupMonkeyException('%s: %s' % (_status.parse_status('snapshot_fetch_error', self._region), e.message),
                subject=_status.parse_status('snapshot_fetch_error', self._region),
                body=e.message,
                category='snapshots')
        log.info('Found %d snapshots', len(snapshots))
        vol_snap_map = {}
        for snapshot in snapshots:
            if not snapshot.description.startswith(self._prefix):
                log.debug('Skipping %s as prefix does not match', snapshot.id)
                continue
            if not snapshot.status == 'completed':
                log.debug('Skipping %s as it is not a complete snapshot', snapshot.id)
                continue
            
            log.debug('Found %s: %s', snapshot.id, snapshot.description)
            vol_snap_map.setdefault(snapshot.volume_id, []).append(snapshot)
            
        for volume_id, most_recent_snapshots in vol_snap_map.iteritems():
            most_recent_snapshots.sort(key=lambda s: s.start_time, reverse=True)
            num_snapshots = len(most_recent_snapshots)
            log.info('Found %d snapshots for %s', num_snapshots, volume_id)

            for i in range(self._snapshots_per_volume, num_snapshots):
                snapshot = most_recent_snapshots[i]
                snapshot_id = snapshot.id
                snapshot_description = snapshot.description
                self._info(subject=_status.parse_status('snapshot_delete', (snapshot_id, snapshot_description)), 
                    src_snapshot=snapshot_id,
                    src_volume=volume_id,
                    category='snapshots')
                try:
                    snapshot.delete()
                    self._info(subject=_status.parse_status('snapshot_delete_success', (snapshot_id, snapshot_description)), 
                        src_snapshot=snapshot_id,
                        category='snapshots')
                except BotoServerError, e:
                    raise BackupMonkeyException('%s: %s' % (_status.parse_status('snapshot_delete_error', (snapshot_id, snapshot_description)), e.message),
                        subject=_status.parse_status('snapshot_delete_error', (snapshot_id, snapshot_description)),
                        body=e.message,
                        src_snapshot=snapshot_id,
                        category='snapshots')
        return True
    
class ErrorFilter(object):
  def filter(self, record):
    return record.levelno >= logging.ERROR

class WarningFilter(object):
  def filter(self, record):
    return record.levelno <= logging.WARNING

class Logging(object):
    # Logging formats
    _log_simple_format = '%(asctime)s [%(levelname)s] %(message)s'
    _log_detailed_format = '%(asctime)s [%(levelname)s] [%(name)s(%(lineno)s):%(funcName)s] %(message)s'
    _log_date_format = '%F %T'

    def getHandler(self, stream, format_, handler_filter):
        _handler = logging.StreamHandler(stream)
        _handler.setFormatter(logging.Formatter(format_, self._log_date_format))
        if handler_filter:
            _handler.addFilter(handler_filter)
        return _handler
    
    def clearLoggingHandlers(self, logger):
        while len(logger.handlers) > 0:
            logger.removeHandler(logger.handlers[0])

    def configure(self, verbosity = None, module = __name__):
        ''' Configure the logging format and verbosity '''
        _log = logging.getLogger(module)
        self.clearLoggingHandlers(_log)
        # Configure our logging output
        if verbosity >= 2:
            _log.addHandler(self.getHandler(stream=sys.stdout, format_=self._log_detailed_format, handler_filter=WarningFilter()))
            _log.addHandler(self.getHandler(stream=sys.stderr, format_=self._log_detailed_format, handler_filter=ErrorFilter()))
            _log.setLevel(level=logging.DEBUG)
        elif verbosity >= 1:
            _log.addHandler(self.getHandler(stream=sys.stdout, format_=self._log_detailed_format, handler_filter=WarningFilter()))
            _log.addHandler(self.getHandler(stream=sys.stderr, format_=self._log_detailed_format, handler_filter=ErrorFilter()))
            _log.setLevel(level=logging.INFO)
        else:
            _log.addHandler(self.getHandler(stream=sys.stdout, format_=self._log_simple_format , handler_filter=WarningFilter()))
            _log.addHandler(self.getHandler(stream=sys.stderr, format_=self._log_simple_format, handler_filter=ErrorFilter()))
            _log.setLevel(level=logging.INFO)

        # Configure Boto's logging output
        if verbosity >= 4:
            logging.getLogger('boto').setLevel(logging.DEBUG)
        elif verbosity >= 3:
            logging.getLogger('boto').setLevel(logging.INFO)
        else:
            logging.getLogger('boto').setLevel(logging.CRITICAL)

