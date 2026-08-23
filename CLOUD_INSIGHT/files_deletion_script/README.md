# SFTP Archive Cleanup Script



Standalone Python script that deletes files from the archive folder **on the SFTP
server** based on file age. The script runs on the Windows server, connects with the
`Utils` package (`Utils.SFTPClient`) and every delete happens on the SFTP location.
Replaces the Talend based cleanup process.

Plain function based script, no classes, one function per operation.

## Files

| File | Purpose |
|------|---------|
| `sftp_cleanup.py` | The cleanup script |
| `DATA\CONFIG\cleanup-config.json` | All runtime settings, including the SFTP connection |
| `Utils\` | Shared package, `Utils.SFTPClient` builds the SFTP connection |
| `DATA\LOG_OUTPUT\` | Default location of the log files and the CSV audit report |

The configuration file path is fixed in the script
(`CONFIG_FILE_PATH` = `DATA\CONFIG\cleanup-config.json`, resolved against the script
folder). It is not a command line argument, so the scheduled task never has to pass it.

## Requirements

- Python 3.6 or higher
- `pysftp` and `paramiko` (used by `Utils.SFTPClient`)
- The `Utils` folder next to `sftp_cleanup.py`
- The SFTP private key file, and delete permission for that account on the archive folder
- Write permission on the local log folder

`Utils.SFTPClient` authenticates with a **private key only** (`keyfile` + `keyPhrase`)
and connects on the default port 22. Password login or a different port would need a
change in `Utils\SFTPClient.py`, not in this script.

## Usage

```
python sftp_cleanup.py <n_days> <-recursive_deletion | -not_recursive_deletion> [options]
```

| Argument | Meaning |
|----------|---------|
| `<n_days>` | Delete files older than this many days |
| `-recursive_deletion` | Clean the archive folder and all sub folders |
| `-not_recursive_deletion` | Clean only the top level of the archive folder |
| `-path <remote folder>` | Override `archiveFolderPath` from the configuration file |
| `-dry_run` | Report what would be deleted without deleting anything |
| `-help` | Show the usage text |

### Examples

```powershell
# delete files older than 30 days, including sub folders
python sftp_cleanup.py 30 -recursive_deletion

# only the top level of the remote archive folder
python sftp_cleanup.py 15 -not_recursive_deletion

# safe preview, deletes nothing
python sftp_cleanup.py 30 -recursive_deletion -dry_run

# a different remote folder, same configuration file
python sftp_cleanup.py 30 -recursive_deletion -path /inbound/ARCHIVE2
```

To run against a second archive with completely different settings, copy the whole
script folder, or edit `DATA\CONFIG\cleanup-config.json` — there is no `-config` option.

`n_days` and the recursion flag are optional. When they are not given the values
`daysOld` and `recursive` from the configuration file are used, so the script can also
be scheduled with no arguments at all.

## Configuration

All runtime settings live in `DATA\CONFIG\cleanup-config.json`, no code change is needed
to change them.

```json
{
  "sftp": {
    "host": "bastion4.chg.e2open.com",
    "user": "ci-sftp",
    "keyfile": "DATA\\CONFIG\\sftpprivatekey.pem",
    "keyPhrase": ""
  },
  "archiveFolderPath": "/inbound/ARCHIVE",
  "daysOld": 30,
  "recursive": true,
  "filePatterns": ["*"],
  "excludePatterns": ["*.tmp", "*.lock", "*.filepart"],
  "excludeFolders": [],
  "logFolderPath": "",
  "logRetentionDays": 90,
  "logEveryNFiles": 1000,
  "writeDeletedFilesReport": true,
  "deleteEmptyFolders": false,
  "dryRun": false,
  "retryCount": 2,
  "retryDelaySeconds": 2,
  "minimumDaysOldAllowed": 1
}
```

| Key | Type | Description |
|-----|------|-------------|
| `sftp.host` | string | SFTP server name |
| `sftp.user` | string | SFTP user |
| `sftp.keyfile` | string | Private key file, a relative path is resolved against the script folder |
| `sftp.keyPhrase` | string | Pass phrase of the key, empty when the key has none |
| `archiveFolderPath` | string | Remote archive folder, forward slashes (required) |
| `daysOld` | number | Delete files older than N days |
| `recursive` | true/false | Include sub folders |
| `filePatterns` | list | Only files matching one of these wildcard patterns are considered, `["*"]` = all |
| `excludePatterns` | list | File name patterns that must never be deleted (in progress uploads etc.) |
| `excludeFolders` | list | Remote sub folder names that are not scanned at all |
| `logFolderPath` | string | Local folder for logs and the CSV report, empty = `DATA\LOG_OUTPUT` next to the script |
| `logRetentionDays` | number | Old cleanup logs/reports are removed after this many days, 0 = keep forever |
| `logEveryNFiles` | number | Write a progress line every N scanned files |
| `writeDeletedFilesReport` | true/false | Write the CSV list of deleted files (audit trail) |
| `deleteEmptyFolders` | true/false | Also remove remote sub folders left empty (never removes the archive root) |
| `dryRun` | true/false | Report only, delete nothing |
| `retryCount` | number | How many times a failed delete is retried |
| `retryDelaySeconds` | number | Wait time between retries |
| `minimumDaysOldAllowed` | number | Safety limit, the script refuses to run with a smaller `daysOld` |

Patterns are matched case insensitively. File age uses the modification time
reported by the SFTP server, so the server clock has to be correct.

## Output

Two files per run, written locally in `logFolderPath`:

| File | Content |
|------|---------|
| `sftp_cleanup_YYYYMMDD_HHMMSS.log` | Full execution log |
| `sftp_cleanup_deleted_files_YYYYMMDD_HHMMSS.csv` | One row per deleted file: `deleted_at, remote_file_path, size_bytes, last_modified, status` |

The log contains the script start/end, every setting used for the run, every deleted
file, every failure, progress lines and the summary block:

```
2026-08-06 15:23:23 - INFO - SFTP ARCHIVE CLEANUP STARTED AT 2026-08-06 15:23:23
2026-08-06 15:23:23 - INFO - SFTP host           : bastion4.chg.e2open.com
2026-08-06 15:23:23 - INFO - Archive folder      : /inbound/ARCHIVE
2026-08-06 15:23:23 - INFO - Deletion mode       : RECURSIVE
2026-08-06 15:23:23 - INFO - SFTP connection established
2026-08-06 15:23:23 - INFO - DELETED : /inbound/ARCHIVE/old_root.txt (12.00 B)
2026-08-06 15:23:24 - INFO - PROGRESS : scanned=1000 deleted=812 skipped=188 failed=0 freed=2.10 GB
2026-08-06 15:23:24 - INFO - CLEANUP EXECUTION SUMMARY
2026-08-06 15:23:24 - INFO - Folders scanned       : 3
2026-08-06 15:23:24 - INFO - Files scanned         : 8
2026-08-06 15:23:24 - INFO - Files deleted         : 5
2026-08-06 15:23:24 - INFO - Files skipped         : 3
2026-08-06 15:23:24 - INFO - Files failed          : 0
2026-08-06 15:23:24 - INFO - Empty folders deleted : 1
2026-08-06 15:23:24 - INFO - SFTP reconnects       : 1
2026-08-06 15:23:24 - INFO - Space freed           : 80.00 B
```

Skipped files are logged at DEBUG level so a normal run does not produce one line per
file that stays; the skipped count is always in the summary.

Errors raised inside `Utils.SFTPClient` land in the same log file: the script
configures the root logger, and `SFTPClient` logs through `logging.getLogger("")`
as long as `Utils.Logger` was not initialised.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Completed, nothing failed |
| 1 | Fatal error, no cleanup was done (bad configuration, SFTP connection failed, archive folder unreachable) |
| 2 | Completed, but some files or folders could not be deleted, check the log |

Useful for Task Scheduler alerting: anything other than 0 needs a look.

## Testing without deleting anything

```powershell
python sftp_cleanup.py 30 -recursive_deletion -dry_run
```

The delete call sits behind a single `if dry_run:` branch, nothing is removed. The log
says `WOULD DELETE`, the summary says `(DRY RUN)` and the CSV rows carry the status
`DRY_RUN`. Review the CSV before the first real run:

```powershell
$csv = Get-ChildItem .\DATA\LOG_OUTPUT\sftp_cleanup_deleted_files_*.csv |
       Sort-Object LastWriteTime | Select-Object -Last 1
Import-Csv $csv.FullName | Select-Object remote_file_path, last_modified, size_bytes | Out-GridView
```

Setting `"dryRun": true` in the config forces dry run regardless of the command line,
which is a safe way to let the first scheduled runs report only.

## Handling large volumes

- `listdir_attr()` returns the name, the size and the modification time of every entry
  of a folder in a single round trip, so there is no extra stat call per file. This is
  the main reason the script is faster than the Talend job.
- The remote tree is walked with a stack of folder names, only the listing of the folder
  that is being processed is held in memory, and files are deleted while the scan is
  still running. Memory usage stays flat for archive folders with a very large number
  of files.
- One SFTP connection is used for the whole run.
- A progress line is written every `logEveryNFiles` files and the CSV report is flushed
  at the same time, so a long run can be followed live.

## Error handling and recovery

- A file that cannot be deleted is logged, counted and the run continues with the next file.
- A failed delete is retried `retryCount` times, `retryDelaySeconds` apart.
- When the error looks like a lost connection the script reconnects to the SFTP server
  and retries immediately, instead of losing the whole run. The number of reconnects is
  in the summary.
- A folder listing that fails is also retried once after a reconnect.
- A file that disappeared in the meantime (another process deleted it) counts as success.
- Symbolic links are never followed and never deleted.
- Ctrl+C stops the run cleanly and still writes the summary and the CSV report.
- The SFTP connection is always closed and the summary is always written, also after a
  fatal error.
- `minimumDaysOldAllowed` blocks a run with a wrong or missing `daysOld` value.

## Scheduling with Windows Task Scheduler

```powershell
$taskName   = "SFTP-Archive-Cleanup"
$scriptPath = "D:\scripts\folder_deletion_script\sftp_cleanup.py"

$action = New-ScheduledTaskAction -Execute "python.exe" `
  -Argument "`"$scriptPath`" 30 -recursive_deletion" `
  -WorkingDirectory "D:\scripts\folder_deletion_script"

$trigger = New-ScheduledTaskTrigger -Daily -At 02:00AM

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -RunLevel Highest
```

Check the result:

```powershell
Get-ScheduledTaskInfo -TaskName "SFTP-Archive-Cleanup"
Get-ChildItem D:\scripts\folder_deletion_script\DATA\LOG_OUTPUT -Filter "sftp_cleanup_*.log" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1 |
  ForEach-Object { Get-Content $_.FullName -Tail 25 }
```

The account running the task must be able to read the private key file.

## Function overview

Every operation is its own function.

| Function | Purpose |
|----------|---------|
| `print_usage` | Show the usage text |
| `parse_arguments` | Read `n_days`, the recursion flag and the options from the command line |
| `load_configuration` | Read the JSON config and merge it with the defaults |
| `apply_command_line_overrides` | Command line values win over the config file |
| `validate_configuration` | Check and normalise every setting |
| `build_sftp_config` | Build the host/user/keyfile/keyPhrase dictionary for `Utils.SFTPClient` |
| `get_log_folder` | Work out where logs are written |
| `setup_logging` | Start logging to the timestamped log file and the console |
| `log_configuration` | Log the settings used for this run |
| `cleanup_old_log_files` | Remove logs/reports older than `logRetentionDays` |
| `open_sftp_session` | Build the SFTP connection with `Utils.SFTPClient` |
| `get_sftp_handle` | Return the pysftp connection behind the Utils client |
| `close_sftp_session` | Close the SFTP connection |
| `looks_like_connection_error` | Tell a connection failure apart from a file failure |
| `reconnect_sftp_session` | Recovery, build a fresh connection after the old one died |
| `check_remote_folder` | Verify the remote archive folder exists and can be listed |
| `normalise_remote_path` / `join_remote_path` | Remote path handling with forward slashes |
| `get_cutoff_timestamp` | Turn N days into the cut off timestamp |
| `format_size` | Byte count into a readable size |
| `is_remote_directory` / `is_remote_symlink` | Entry type of a listing entry |
| `is_folder_excluded` | Should a remote sub folder be skipped |
| `matches_file_patterns` / `matches_exclude_patterns` | Include and exclude pattern matching |
| `list_remote_folder` | Read one remote folder, with reconnect and retry |
| `iterate_remote_files` | Walk the remote tree and yield files one by one |
| `should_delete_file` | Decide if one file has to be deleted |
| `is_file_missing_error` | Recognise "already gone" as success |
| `delete_remote_file` | Delete one remote file with retry and reconnect |
| `open_deleted_files_report` / `write_report_row` | CSV audit report |
| `create_statistics` | The counters used for the summary |
| `run_cleanup` | The main scan and delete loop |
| `delete_remote_empty_folders` | Remove remote sub folders left empty |
| `log_summary` | Write the summary statistics |
| `get_exit_code` | Turn the counters into the exit code |
| `main` | Wire everything together |

## Troubleshooting

| Problem | What to check |
|---------|---------------|
| `ModuleNotFoundError: No module named 'Utils'` | The `Utils` folder must sit next to `sftp_cleanup.py` |
| `ImportError: cannot import name 'DSSKey' from 'paramiko'` | Newer paramiko dropped DSSKey; `Utils\SFTPClient.py` patches this before importing pysftp, so always import through `Utils`, never `import pysftp` directly |
| `SFTP private key file not found` | `sftp.keyfile` path, relative paths are resolved against the script folder |
| `SFTP connection to ... failed` | Host, user, key and pass phrase, plus firewall access from the Windows server |
| `Archive folder does not exist on the SFTP server` | `archiveFolderPath`, remember it is the path as the SFTP user sees it, and it may be relative to that user's home folder |
| `FAILED TO DELETE ... Permission denied` | The SFTP account needs delete permission on the archive folder |
| Many reconnects in the summary | Server side idle timeout or an unstable link, the run still completes but is slower |
| Nothing gets deleted | Run with `-dry_run`, check `daysOld`, `filePatterns` and `excludePatterns` |
| Wrong files were deleted | The CSV report of the run lists exactly what was removed and when |
