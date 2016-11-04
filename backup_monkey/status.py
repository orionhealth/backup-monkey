
class BackupMonkeyStatus(object):
  messages = {
    'cross_account_connect': 'Creating cross account connection to `%s` account using `%s` role on `%s` region',
    'cross_account_error': 'Cannot complete cross account connection',
    'region_connect': 'Connecting to `%s` region',
    'region_connect_error': 'Cannot complete connection to `%s` region',
    'region_connect_invalid': 'Cannot complete connection to `%s` region. Check to make sure you are connecting to a valid region',
    'tags_invalid': 'You have passed an invalid --tags parameter. Please make sure you follow the form: --tags name:value',
    'volumes_fetch': 'Fetching volumes on `%s` region',
    'volumes_fetch_error': 'Cannot fetch volumes on `%s` region',
    'volume_describe': 'Parsing information on volume `%s`',
    'volume_describe_error': 'Cannot parse information on volume `%s`',
    'snapshots_fetch': 'Fetching snapshots on `%s` region',
    'snapshots_fetch_error': 'Cannot fetch snapshots on `%s` region',
    'snapshot_create': 'Creating snapshot of volume `%s` and setting a description of `%s`',
    'snapshot_create_success': 'Successfully created snapshot `%s` from volume `%s`',
    'snapshot_create_error': 'Cannot create snapshot of volume `%s`',
    'snapshot_delete': 'Deleting snapshot `%s` with a description of `%s`',
    'snapshot_delete_success': 'Successfully deleted snapshot `%s` with a description of `%s`',
    'snapshot_delete_error': 'Cannot delete snapshot `%s` with a description of `%s`',
    'retry_after_sleep': '`%s` attmpts fails and waiting `%s` seconds then retry',
    'retry_all_fail': 'Total `%s` retries fail and give up'
  }

  @staticmethod
  def parse_status(key, sub=None):
    if sub:
      if type(sub) == type(tuple()):
        return eval('"' + BackupMonkeyStatus.messages[key] + '" % ' + str(sub))
      else:
        return eval('"' + BackupMonkeyStatus.messages[key] + '" % "' + sub + '"')
    else:
      return BackupMonkeyStatus.messages[key]
