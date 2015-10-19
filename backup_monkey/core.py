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
import logging
import sys

from boto.exception import NoAuthHandlerFound
from boto import ec2

from exception import BackupMonkeyException

__all__ = ('BackupMonkey', 'Logging')
log = logging.getLogger(__name__)

class BackupMonkey(object):
    def __init__(self, region, max_snapshots_per_volume, tags, reverse_tags, cross_account_number, cross_account_role):
        self._region = region
        self._prefix = 'BACKUP_MONKEY'
        self._snapshots_per_volume = max_snapshots_per_volume
        self._tags = tags
        self._reverse_tags = reverse_tags
        self._cross_account_number = cross_account_number
        self._cross_account_role = cross_account_role
        self._conn = self.get_connection()

    def get_connection(self):
        ret = None
        if self._cross_account_number and self._cross_account_role:
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
            except Exception,e:
                print e
                raise BackupMonkeyException('Cannot complete cross account access')
        else:
            log.info("Connecting to region %s", self._region)
            try:
                ret = ec2.connect_to_region(self._region)
            except NoAuthHandlerFound:
                log.error('Could not connect to region %s' % self._region)
                log.critical('No AWS credentials found. To configure Boto, please read: http://boto.readthedocs.org/en/latest/boto_config_tut.html')
                raise BackupMonkeyException('No AWS credentials found')            
        if not ret:
            raise BackupMonkeyException('Could not connect to region `%s`. Check to make sure you are connecting to a valid region' % self._region)
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
        except ValueError:
            log.error('Invalid tag parameter')
            raise BackupMonkeyException('Invalid tag parameter')
        if not self._reverse_tags:
            for f in filters.keys():
                filters['tag:%s' % f] = filters.pop(f)
        return filters

    def get_volumes_to_snapshot(self):
        volumes = [] 
        if self._reverse_tags:
            filters = self.get_filters()
            black_list = []
            for f in filters.keys():
                if isinstance(filters[f], list):
                    black_list = black_list + [(f, i) for i in filters[f]]
                else:
                    black_list.append((f, filters[f]))
            for v in self._conn.get_all_volumes():
                if len(set(v.tags.items()) - set(black_list)) == len(set(v.tags.items())):
                    volumes.append(v) 
        else:
            if self._tags:
                return self._conn.get_all_volumes(filters=self.get_filters())
            else:
                volumes = self._conn.get_all_volumes()
        return volumes
    
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
            log.info('Creating snapshot of %s: %s', volume.id, description)
            volume.create_snapshot(description)
        return True


    def remove_old_snapshots(self):
        ''' Loop through this account's snapshots, and remove the oldest ones
        where there are more snapshots per volume than required '''
        
        log.info('Configured to keep %d snapshots per volume', self._snapshots_per_volume)
        log.info('Getting list of EBS snapshots')
        snapshots = self._conn.get_all_snapshots(owner='self')
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
                log.info(' Deleting %s: %s', snapshot.id, snapshot.description)
                snapshot.delete()
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

