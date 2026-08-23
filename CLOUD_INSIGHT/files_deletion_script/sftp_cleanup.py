"""
ARCHIVE FOLDER CLEANUP SCRIPT (LOCAL / SFTP)
--------------------------------------------
Reads the configuration file and deletes the files that are older than N days
from every folder listed in the configuration.

The same script cleans two different environments:

    -env=local   every delete happens on the local Windows server
    -env=sftp    every delete happens on the SFTP server, the connection is
                 built with the Utils package (Utils.SFTPClient)
                 -env=ftp is accepted as an alias of -env=sftp

Usage:
    python sftp_cleanup.py -env=local|sftp -dryrun=no|yes [-config=<file>]

Examples:
    python sftp_cleanup.py -env=local -dryrun=yes
    python sftp_cleanup.py -env=sftp  -dryrun=no
    python sftp_cleanup.py -env=sftp  -dryrun=no
    python sftp_cleanup.py -env=sftp  -dryrun=yes -config=test-config.json

Everything else comes from the configuration file: the folder list, the age in
days per folder and the recursion mode per folder.

    {
        "sftp": {
            "URL": "", "UserName": "", "Passphrase": "",
            "Fingerprint": "", "SecretKeyPath": "",
            "Paths": [
                { "Path": "/CI_SFTP/ci-sftp/inbound/HMC/Archive/",
                  "Age": "7", "Recurse": "No" }
            ]
        }
    }

When a folder from the configuration cannot be found in the environment the
script is running against, it reports

    running env: <env> not found <path>

and carries on with the next folder, the exit code becomes 2.

Exit codes:
    0 = completed successfully
    1 = fatal error (bad config / SFTP connection)
    2 = completed but a folder was not found or a file could not be deleted
"""

from datetime import datetime, timedelta
import csv
import errno
import json
import logging
import os
import stat
import sys
import time

# the Utils package sits next to this script, make sure it is importable
# also when the script is started from another working directory
BaseDirectory = os.path.dirname(os.path.realpath(__file__))
if BaseDirectory not in sys.path:
    sys.path.insert(0, BaseDirectory)

from Utils import *

# the configuration file is fixed, it always sits in the CONFIG folder next to
# this script so the scheduled task does not need to pass a path.
# -config=<file> is only there for testing with another file.
DEFAULT_CONFIG_FILE_PATH = os.path.join(BaseDirectory, "DATA", "CONFIG", "cleanup-config.json")
DEFAULT_LOG_FOLDER = os.path.join(BaseDirectory, "DATA", "LOG_OUTPUT")

# the two environments the script can clean, -env=ftp is treated as sftp
ENVIRONMENT_LOCAL = "local"
ENVIRONMENT_SFTP = "sftp"
ENVIRONMENT_ALIASES = {"local": ENVIRONMENT_LOCAL,
                       "sftp": ENVIRONMENT_SFTP,
                       "ftp": ENVIRONMENT_SFTP}

# optional keys that may be added at the top level of the configuration file,
# the values below are used when they are missing
DEFAULT_OPTIONS = {
    "logFolderPath": "",
    "logRetentionDays": 90,
    "logEveryNFiles": 1000,
    "writeDeletedFilesReport": True,
    "deleteEmptyFolders": False,
    "retryCount": 2,
    "retryDelaySeconds": 2,
    "minimumDaysOldAllowed": 1,
}

# error texts that mean the SFTP connection itself is gone and a reconnect is worth trying
CONNECTION_ERROR_TEXTS = [
    "socket", "closed", "eof", "connection", "broken pipe",
    "timed out", "timeout", "not connected", "no route", "reset by peer",
]

# error texts that mean the account is not allowed to delete the file. Waiting and
# trying again cannot change that, so a retry only wastes time: retrying every file
# of a large archive folder three times adds hours to the run for nothing.
PERMISSION_ERROR_TEXTS = [
    "permission denied", "access is denied", "operation not permitted",
]


# ---------------------------------------------------------------------------
# 1. COMMAND LINE ARGUMENTS
# ---------------------------------------------------------------------------

def print_usage():
    """Print how the script is supposed to be called."""
    print("Usage: python sftp_cleanup.py -env=local|sftp -dryrun=no|yes [-config=<file>]")
    print("")
    print("  -env=local      delete the files on this local server")
    print("  -env=sftp       delete the files on the SFTP server (-env=ftp means the same)")
    print("  -dryrun=yes     report what would be deleted, delete nothing")
    print("  -dryrun=no      really delete the files (default)")
    print("")
    print("Optional:")
    print("  -config=<file>  use another configuration file, for testing")
    print("  -help           show this message")
    print("")
    print("Folder list, age in days and recursion mode always come from the")
    print("configuration file: DATA\\CONFIG\\cleanup-config.json")


def parse_yes_no(argument_name, value):
    """Turn yes / no (also true / false, y / n, 1 / 0) into a boolean."""
    lowered = str(value).strip().lower()

    if lowered in ("yes", "y", "true", "1"):
        return True
    if lowered in ("no", "n", "false", "0"):
        return False

    raise ValueError("%s must be yes or no, got: %s" % (argument_name, value))


def parse_environment(value):
    """Turn the -env value into 'local' or 'sftp'."""
    lowered = str(value).strip().lower()

    if lowered not in ENVIRONMENT_ALIASES:
        raise ValueError("-env must be local, sftp or ftp, got: %s" % value)

    return ENVIRONMENT_ALIASES[lowered]


def split_argument(argument):
    """Split '-env=local' into ('-env', 'local'), the separator may also be a space."""
    if "=" in argument:
        name, value = argument.split("=", 1)
        return name.strip().lower(), value.strip()
    return argument.strip().lower(), None


def parse_arguments(argv):
    """Read the command line arguments and return them as a dictionary."""
    arguments = {
        "environment": None,
        "dry_run": False,
        "config_path": DEFAULT_CONFIG_FILE_PATH,
        "show_help": False,
    }

    index = 0
    while index < len(argv):
        name, value = split_argument(argv[index])

        # '-env local' is accepted as well as '-env=local'
        if value is None and name in ("-env", "--env", "-dryrun", "--dryrun", "-config", "--config"):
            index = index + 1
            if index >= len(argv):
                raise ValueError("%s was given without a value" % name)
            value = argv[index]

        if name in ("-help", "--help", "-h", "/?"):
            arguments["show_help"] = True

        elif name in ("-env", "--env"):
            arguments["environment"] = parse_environment(value)

        elif name in ("-dryrun", "--dryrun", "-dry_run", "--dry_run"):
            arguments["dry_run"] = parse_yes_no("-dryrun", value)

        elif name in ("-config", "--config"):
            arguments["config_path"] = value if os.path.isabs(value) \
                else os.path.join(BaseDirectory, value)

        else:
            raise ValueError("Unknown argument: %s" % argv[index])

        index = index + 1

    if not arguments["show_help"] and arguments["environment"] is None:
        raise ValueError("-env is missing, pass -env=local or -env=sftp")

    return arguments


# ---------------------------------------------------------------------------
# 2. CONFIGURATION
# ---------------------------------------------------------------------------

def load_configuration(config_path):
    """Read the JSON configuration file."""
    if not os.path.isfile(config_path):
        raise IOError("Configuration file not found: %s" % config_path)

    with open(config_path, "r") as config_file:
        config = json.load(config_file)

    if not isinstance(config, dict):
        raise ValueError("Configuration file must contain a JSON object: %s" % config_path)

    return config


def get_sftp_section(config):
    """Return the 'sftp' block of the configuration file."""
    sftp_section = config.get("sftp")

    if not isinstance(sftp_section, dict) or not sftp_section:
        raise ValueError("The 'sftp' block is missing in the configuration file")

    return sftp_section


def get_options(config):
    """Read the optional top level keys and fall back to the defaults."""
    options = dict(DEFAULT_OPTIONS)

    for key in options:
        if key in config:
            options[key] = config[key]

    options["logRetentionDays"] = max(0, int(options["logRetentionDays"]))
    options["logEveryNFiles"] = max(1, int(options["logEveryNFiles"]))
    options["retryCount"] = max(0, int(options["retryCount"]))
    options["retryDelaySeconds"] = max(0, int(options["retryDelaySeconds"]))
    options["minimumDaysOldAllowed"] = max(0, int(options["minimumDaysOldAllowed"]))
    options["writeDeletedFilesReport"] = bool(options["writeDeletedFilesReport"])
    options["deleteEmptyFolders"] = bool(options["deleteEmptyFolders"])

    return options


def parse_path_entry(entry, entry_number, environment, minimum_days):
    """
    Turn one element of the 'Paths' list into a clean dictionary:
    path, age (int) and recurse (bool).

    The SFTP folder and the local folder are the same storage but they are not
    reached through the same path (/CI_SFTP/ci-sftp/inbound/... over SFTP,
    Z:\\inbound\\... or a UNC path on the Windows server). An entry may therefore
    carry an optional 'LocalPath' that is used for -env=local, when it is missing
    'Path' is used for both environments.
    """
    if not isinstance(entry, dict):
        raise ValueError("Paths entry %d must be a JSON object" % entry_number)

    raw_path = str(entry.get("Path", "")).strip()
    if environment == ENVIRONMENT_LOCAL and str(entry.get("LocalPath", "")).strip():
        raw_path = str(entry["LocalPath"]).strip()

    if not raw_path:
        raise ValueError("Paths entry %d has an empty 'Path'" % entry_number)

    try:
        age_in_days = int(str(entry.get("Age", "")).strip())
    except ValueError:
        raise ValueError("Paths entry %d has a bad 'Age' (%s), a whole number is expected"
                         % (entry_number, entry.get("Age")))

    if age_in_days < minimum_days:
        raise ValueError(
            "Paths entry %d has Age=%d which is below minimumDaysOldAllowed (%d). "
            "This safety check stops the script from wiping a whole folder. Path: %s"
            % (entry_number, age_in_days, minimum_days, raw_path))

    recurse = parse_yes_no("Paths entry %d 'Recurse'" % entry_number, entry.get("Recurse", "No"))

    return {
        "path": normalise_path(raw_path, environment),
        "age": age_in_days,
        "recurse": recurse,
    }


def get_path_entries(sftp_section, environment, minimum_days):
    """Read and validate the 'Paths' list of the configuration file."""
    raw_entries = sftp_section.get("Paths")

    if not isinstance(raw_entries, list) or len(raw_entries) == 0:
        raise ValueError("The 'Paths' list is missing or empty in the configuration file")

    entries = []
    entry_number = 0
    for raw_entry in raw_entries:
        entry_number = entry_number + 1
        entries.append(parse_path_entry(raw_entry, entry_number, environment, minimum_days))

    return entries


def build_sftp_config(sftp_section):
    """
    Map the configuration keys onto the dictionary Utils.SFTPClient expects:
    URL -> host, UserName -> user, SecretKeyPath -> keyfile, Passphrase -> keyPhrase.
    The Utils package is used as it is, so the mapping happens here.
    A relative key path is resolved against the script folder so the script also
    works when it is started by the Task Scheduler from another folder.
    """
    host = str(sftp_section.get("URL", "")).strip()
    user = str(sftp_section.get("UserName", "")).strip()
    key_file = str(sftp_section.get("SecretKeyPath", "")).strip()

    if not host:
        raise ValueError("sftp.URL is empty in the configuration file")
    if not user:
        raise ValueError("sftp.UserName is empty in the configuration file")
    if not key_file:
        raise ValueError("sftp.SecretKeyPath is empty in the configuration file")

    if not os.path.isabs(key_file):
        key_file = os.path.join(BaseDirectory, key_file)

    if not os.path.isfile(key_file):
        raise IOError("SFTP private key file not found: %s" % key_file)

    # an empty pass phrase must be sent as None, not as an empty string
    pass_phrase = str(sftp_section.get("Passphrase", "")).strip()

    return {
        "host": host,
        "user": user,
        "keyfile": key_file,
        "keyPhrase": pass_phrase if pass_phrase else None,
    }


def get_log_folder(options):
    """Return the local folder where the log file and the report are written."""
    log_folder = str(options.get("logFolderPath", "")).strip()
    if not log_folder:
        return DEFAULT_LOG_FOLDER
    if not os.path.isabs(log_folder):
        return os.path.join(BaseDirectory, log_folder)
    return log_folder


# ---------------------------------------------------------------------------
# 3. PATH HELPERS
# ---------------------------------------------------------------------------

def normalise_path(raw_path, environment):
    """
    Clean a path from the configuration file.
    SFTP always uses forward slashes, a local path is turned into the Windows
    form so the log lines show the path the way the server sees it.
    """
    cleaned = str(raw_path).strip().replace("\\", "/")

    while cleaned.endswith("/") and len(cleaned) > 1:
        cleaned = cleaned[:-1]

    if environment == ENVIRONMENT_LOCAL:
        return os.path.normpath(cleaned)

    return cleaned


def join_path(folder_path, name, environment):
    """Join a folder and a file name for the environment that is being cleaned."""
    if environment == ENVIRONMENT_LOCAL:
        return os.path.join(folder_path, name)

    if folder_path.endswith("/"):
        return folder_path + name
    return folder_path + "/" + name


def get_cutoff_timestamp(age_in_days):
    """Return the epoch timestamp; every file older than this is a deletion candidate."""
    cutoff_datetime = datetime.now() - timedelta(days=age_in_days)
    return cutoff_datetime.timestamp()


def format_size(size_in_bytes):
    """Turn a byte count into a readable string."""
    size = float(size_in_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return "%.2f %s" % (size, unit)
        size = size / 1024.0
    return "%.2f PB" % size


# ---------------------------------------------------------------------------
# 4. LOGGING
# ---------------------------------------------------------------------------

def setup_logging(log_folder, run_stamp):
    """
    Start logging to a timestamped log file and to the console.
    The root logger is configured on purpose: Utils.SFTPClient logs its own
    errors through logging.getLogger(Logger.eventID), which is the root logger
    as long as Utils.Logger was not initialised, so SFTP errors land in the
    same log file.
    """
    if not os.path.isdir(log_folder):
        os.makedirs(log_folder)

    log_file_path = os.path.join(log_folder, "sftp_cleanup_%s.log" % run_stamp)

    logging.basicConfig(filename=log_file_path,
                        filemode="a",
                        format="%(asctime)s - %(levelname)s - %(message)s",
                        level=logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logging.getLogger().addHandler(console_handler)

    # paramiko is very chatty on INFO level, keep the cleanup log readable
    logging.getLogger("paramiko").setLevel(logging.WARNING)

    return log_file_path


def log_configuration(environment, dry_run, config_path, log_file_path,
                      sftp_section, path_entries, options):
    """Write the settings used for this run into the log (needed for audits)."""
    logging.info("Running env         : %s", environment)
    logging.info("Config file         : %s", config_path)
    logging.info("Log file            : %s", log_file_path)
    logging.info("Dry run             : %s", "YES" if dry_run else "NO")

    if environment == ENVIRONMENT_SFTP:
        logging.info("SFTP URL            : %s", sftp_section.get("URL"))
        logging.info("SFTP user           : %s", sftp_section.get("UserName"))
        logging.info("SFTP key file       : %s", sftp_section.get("SecretKeyPath"))
        fingerprint = str(sftp_section.get("Fingerprint", "")).strip()
        if fingerprint:
            # Utils.SFTPClient is used unmodified and it disables the host key
            # check, the fingerprint is only written to the log
            logging.info("SFTP fingerprint    : %s (not verified, host key check is off)",
                         fingerprint)

    logging.info("Folders to clean    : %d", len(path_entries))
    for entry in path_entries:
        logging.info("  %s | older than %d day(s) | %s",
                     entry["path"], entry["age"],
                     "RECURSIVE" if entry["recurse"] else "NOT RECURSIVE")

    logging.info("Delete empty folders: %s", options["deleteEmptyFolders"])
    logging.info("Retry on failure    : %d time(s), %d second(s) apart",
                 options["retryCount"], options["retryDelaySeconds"])


def log_path_not_found(environment, path):
    """
    The error the requirement asks for, used for both environments:
        running env: local not found D:\\...
        running env: sftp not found /CI_SFTP/...
    """
    logging.error("running env: %s not found %s", environment, path)


def cleanup_old_log_files(log_folder, log_retention_days):
    """Delete old log files and old reports so the log folder does not grow forever."""
    if log_retention_days <= 0:
        return 0

    cutoff_timestamp = time.time() - (log_retention_days * 86400)
    removed_count = 0

    try:
        file_names = os.listdir(log_folder)
    except OSError as error:
        logging.warning("Could not read the log folder %s : %s", log_folder, error)
        return 0

    for file_name in file_names:
        if not file_name.startswith("sftp_cleanup_"):
            continue

        file_path = os.path.join(log_folder, file_name)
        try:
            if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff_timestamp:
                os.remove(file_path)
                removed_count = removed_count + 1
        except OSError as error:
            logging.warning("Could not remove old log file %s : %s", file_path, error)

    if removed_count > 0:
        logging.info("Removed %d log file(s) older than %d day(s)", removed_count, log_retention_days)

    return removed_count


# ---------------------------------------------------------------------------
# 5. SFTP SESSION
# ---------------------------------------------------------------------------

def open_sftp_session(sftp_config):
    """
    Build the SFTP connection with the Utils package.
    The session is a small dictionary so the connection can be replaced by a
    reconnect without passing the client object around everywhere.
    """
    logging.info("Connecting to SFTP server %s as %s ...",
                 sftp_config.get("host"), sftp_config.get("user"))

    try:
        client = SFTPClient(sftp_config)
    except Exception as error:
        # wrong host, wrong user, bad key, firewall ... report it as a clean
        # fatal error instead of a stack trace
        raise IOError("SFTP connection to %s failed : %s" % (sftp_config.get("host"), error))

    session = {"config": sftp_config, "client": client, "reconnects": 0}

    logging.info("SFTP connection established")
    try:
        logging.info("SFTP working folder : %s", client.ClientHandle.pwd)
    except Exception as error:
        logging.warning("Could not read the SFTP working folder : %s", error)

    return session


def get_sftp_handle(session):
    """Return the pysftp connection behind the Utils SFTPClient."""
    return session["client"].ClientHandle


def close_sftp_session(session):
    """Close the SFTP connection."""
    if session is None or session.get("client") is None:
        return

    try:
        get_sftp_handle(session).close()
        logging.info("SFTP connection closed")
    except Exception as error:
        logging.warning("Could not close the SFTP connection cleanly : %s", error)


def looks_like_connection_error(error_text):
    """True when the error text suggests the connection died instead of a file problem."""
    lowered = str(error_text).lower()
    for text in CONNECTION_ERROR_TEXTS:
        if text in lowered:
            return True
    return False


def reconnect_sftp_session(session):
    """
    Recovery: build a fresh connection after the old one died.
    Returns True when the new connection is up.
    """
    session["reconnects"] = session["reconnects"] + 1
    logging.warning("Trying to reconnect to the SFTP server (attempt %d) ...", session["reconnects"])

    try:
        get_sftp_handle(session).close()
    except Exception:
        pass

    try:
        session["client"] = SFTPClient(session["config"])
        logging.info("Reconnected to the SFTP server")
        return True
    except Exception as error:
        logging.error("Reconnect failed : %s", error)
        return False


# ---------------------------------------------------------------------------
# 6. FOLDER CHECK
# ---------------------------------------------------------------------------

def local_folder_exists(folder_path):
    """True when the local path exists and is really a folder."""
    return os.path.isdir(folder_path)


def remote_folder_exists(session, folder_path):
    """
    True when the remote path exists on the SFTP server and is really a folder.
    A dead connection is reconnected once so a long run does not stop here.
    """
    try:
        return get_sftp_handle(session).isdir(folder_path)
    except Exception as error:
        if looks_like_connection_error(error) and reconnect_sftp_session(session):
            try:
                return get_sftp_handle(session).isdir(folder_path)
            except Exception as retry_error:
                error = retry_error

        logging.error("Could not check the folder %s : %s", folder_path, error)
        return False


def folder_exists(environment, session, folder_path):
    """Folder check for the environment that is being cleaned."""
    if environment == ENVIRONMENT_LOCAL:
        return local_folder_exists(folder_path)
    return remote_folder_exists(session, folder_path)


def get_sftp_home_folder(session):
    """Return the folder the SFTP user lands in, for example /CI_SFTP/ci-sftp."""
    try:
        return str(get_sftp_handle(session).pwd)
    except Exception as error:
        logging.warning("Could not read the SFTP working folder : %s", error)
        return ""


def resolve_remote_path(session, folder_path, log_resolution=True):
    """
    Return the remote folder that really exists, or None.

    The SFTP account is chrooted into its own home folder (/CI_SFTP/ci-sftp), so
    a path written as /inbound/... is looked up from the server root and is not
    found. When that happens the same path is tried once more under the SFTP home
    folder, which is what /inbound/... is meant to say.
    """
    if remote_folder_exists(session, folder_path):
        return folder_path

    home_folder = get_sftp_home_folder(session)
    if not home_folder or home_folder == "/":
        return None

    candidate = join_path(home_folder, folder_path.lstrip("/"), ENVIRONMENT_SFTP)
    if candidate != folder_path and remote_folder_exists(session, candidate):
        if log_resolution:
            logging.info("Resolved %s to %s (relative to the SFTP home folder %s)",
                         folder_path, candidate, home_folder)
        return candidate

    return None


def resolve_cleanup_path(environment, session, folder_path, log_resolution=True):
    """Return the folder to clean, or None when it cannot be found."""
    if environment == ENVIRONMENT_LOCAL:
        return folder_path if local_folder_exists(folder_path) else None
    return resolve_remote_path(session, folder_path, log_resolution)


def log_nearest_existing_parent(environment, session, folder_path, max_entries=40):
    """
    After a folder was not found, log the deepest parent that does exist and what
    it holds, so the correct path can be worked out without another run.
    """
    separator = os.sep if environment == ENVIRONMENT_LOCAL else "/"
    current = folder_path

    while separator in current.rstrip(separator):
        current = current.rstrip(separator).rsplit(separator, 1)[0]
        if not current:
            break

        # the same home folder fallback as for the folder itself, so the listing
        # of the SFTP home folder is shown for a path written as /inbound/...
        existing = resolve_cleanup_path(environment, session, current, log_resolution=False)
        if existing is None:
            continue

        statistics = create_statistics()
        names = sorted(entry[0] for entry in list_folder(environment, session,
                                                         existing, statistics))
        shown = ", ".join(names[:max_entries]) or "(empty)"
        if len(names) > max_entries:
            shown = shown + " ... (%d entries in total)" % len(names)

        logging.error("Nearest existing folder is %s and it holds : %s", existing, shown)
        return

    if environment == ENVIRONMENT_SFTP:
        logging.error("The SFTP home folder is %s, a path is looked up from the "
                      "server root unless it exists under the home folder",
                      get_sftp_home_folder(session))


# ---------------------------------------------------------------------------
# 7. FILE LISTING
# ---------------------------------------------------------------------------

def list_local_folder(folder_path, statistics):
    """
    Read one local folder and return a list of
    (name, full_path, is_folder, is_link, size, modification_time).
    """
    entries = []

    try:
        for directory_entry in os.scandir(folder_path):
            try:
                entry_stat = directory_entry.stat(follow_symlinks=False)
            except OSError as error:
                logging.warning("Could not read %s : %s", directory_entry.path, error)
                statistics["errors"] = statistics["errors"] + 1
                continue

            entries.append((directory_entry.name,
                            directory_entry.path,
                            stat.S_ISDIR(entry_stat.st_mode),
                            stat.S_ISLNK(entry_stat.st_mode) or directory_entry.is_symlink(),
                            entry_stat.st_size,
                            entry_stat.st_mtime))
    except OSError as error:
        logging.error("Cannot read folder %s : %s", folder_path, error)
        statistics["folder_errors"] = statistics["folder_errors"] + 1

    return entries


def list_remote_folder(session, folder_path, statistics):
    """
    Read one remote folder and return the same list of tuples as
    list_local_folder. listdir_attr brings the name, the size and the
    modification time in a single round trip, so no extra stat call per file
    is needed. A dead connection is reconnected once and the listing retried.
    """
    attributes_list = None

    try:
        attributes_list = get_sftp_handle(session).listdir_attr(folder_path)
    except Exception as error:
        if looks_like_connection_error(error) and reconnect_sftp_session(session):
            try:
                attributes_list = get_sftp_handle(session).listdir_attr(folder_path)
            except Exception as retry_error:
                error = retry_error

        if attributes_list is None:
            logging.error("Cannot read folder %s : %s", folder_path, error)
            statistics["folder_errors"] = statistics["folder_errors"] + 1
            return []

    entries = []
    for attributes in attributes_list:
        entries.append((attributes.filename,
                        join_path(folder_path, attributes.filename, ENVIRONMENT_SFTP),
                        stat.S_ISDIR(attributes.st_mode),
                        stat.S_ISLNK(attributes.st_mode),
                        attributes.st_size or 0,
                        attributes.st_mtime))
    return entries


def list_folder(environment, session, folder_path, statistics):
    """Folder listing for the environment that is being cleaned."""
    if environment == ENVIRONMENT_LOCAL:
        return list_local_folder(folder_path, statistics)
    return list_remote_folder(session, folder_path, statistics)


def iterate_files(environment, session, root_folder_path, recurse, statistics):
    """
    Walk the folder and yield (file_path, size, modification_time) one at a time.

    A stack of folder names is used instead of recursion, only the listing of the
    folder that is being processed is held in memory. Files are handled while the
    scan is still running, so the memory usage stays flat for archive folders
    with a very large number of files.
    """
    folders_to_scan = [root_folder_path]

    while folders_to_scan:
        current_folder = folders_to_scan.pop()
        statistics["folders_scanned"] = statistics["folders_scanned"] + 1

        sub_folders = []
        for _, entry_path, is_folder, is_link, size, modification_time in \
                list_folder(environment, session, current_folder, statistics):

            if is_link:
                # a symbolic link or a junction is never followed and never deleted,
                # deleting through it would hit files outside the archive folder
                statistics["files_skipped"] = statistics["files_skipped"] + 1
                logging.debug("SKIPPED : %s (link)", entry_path)
            elif is_folder:
                if recurse:
                    sub_folders.append(entry_path)
            else:
                yield entry_path, size, modification_time

        folders_to_scan.extend(sub_folders)


# ---------------------------------------------------------------------------
# 8. DELETION
# ---------------------------------------------------------------------------

def is_file_missing_error(error):
    """True when the delete failed because the file is already gone."""
    lowered = str(error).lower()
    return "no such file" in lowered or "not found" in lowered or \
        "cannot find the file" in lowered


def is_permission_error(error):
    """
    True when the delete failed because the account is not allowed to remove the
    file. On the SFTP side this is nearly always the parent folder: a delete needs
    write and execute on the folder that holds the file, not on the file itself, so
    a folder owned by another account with mode 755 blocks every delete inside it.
    """
    lowered = str(error).lower()
    for text in PERMISSION_ERROR_TEXTS:
        if text in lowered:
            return True

    error_number = getattr(error, "errno", None)
    return error_number in (errno.EACCES, errno.EPERM)


def clear_read_only_attribute(file_path):
    """
    Drop the read only attribute of one file so it can be removed.
    The archive files arrive from Windows with the read only attribute set, and
    os.remove refuses those with 'Access is denied' even when the account owns the
    folder. Returns True when the attribute was cleared.
    """
    try:
        os.chmod(file_path, stat.S_IWRITE | stat.S_IREAD)
        return True
    except OSError:
        return False


def delete_local_file(file_path, retry_count, retry_delay_seconds):
    """
    Delete one file on the local server.
    Returns (True, "") on success or (False, error_text) on failure.
    A file that is still open by another process is the usual reason for a retry.
    """
    attempt = 0
    last_error = ""
    read_only_cleared = False

    while attempt <= retry_count:
        try:
            os.remove(file_path)
            return True, ""
        except OSError as error:
            if isinstance(error, FileNotFoundError) or is_file_missing_error(error):
                # somebody else already removed it, treat it as done
                return True, ""
            last_error = str(error)

            # a read only file is refused with the same error as a file the account
            # may not touch at all, so clear the attribute once and try again right
            # away instead of waiting out the retry delay
            if is_permission_error(error) and not read_only_cleared:
                read_only_cleared = True
                if clear_read_only_attribute(file_path):
                    continue
                return False, last_error

        attempt = attempt + 1
        if attempt <= retry_count and retry_delay_seconds > 0:
            time.sleep(retry_delay_seconds)

    return False, last_error


def delete_remote_file(session, file_path, retry_count, retry_delay_seconds):
    """
    Delete one file on the SFTP server.
    Returns (True, "") on success or (False, error_text) on failure.
    A broken connection is reconnected before the retry, that is the usual reason
    for a failure in the middle of a long cleanup run.
    """
    attempt = 0
    last_error = ""

    while attempt <= retry_count:
        try:
            get_sftp_handle(session).remove(file_path)
            return True, ""
        except Exception as error:
            if is_file_missing_error(error):
                return True, ""
            if is_permission_error(error):
                # the account may not delete inside this folder, another attempt
                # returns the very same error
                return False, str(error)
            last_error = str(error)

        attempt = attempt + 1
        if attempt <= retry_count:
            if looks_like_connection_error(last_error):
                if not reconnect_sftp_session(session):
                    return False, last_error
            elif retry_delay_seconds > 0:
                time.sleep(retry_delay_seconds)

    return False, last_error


def delete_file(environment, session, file_path, retry_count, retry_delay_seconds):
    """Delete one file in the environment that is being cleaned."""
    if environment == ENVIRONMENT_LOCAL:
        return delete_local_file(file_path, retry_count, retry_delay_seconds)
    return delete_remote_file(session, file_path, retry_count, retry_delay_seconds)


def get_parent_folder(file_path, environment):
    """Return the folder that holds the file, that is the folder the rights sit on."""
    if environment == ENVIRONMENT_LOCAL:
        return os.path.dirname(file_path)
    return file_path.rsplit("/", 1)[0] if "/" in file_path else file_path


def log_permission_denied_hint(environment, session, file_path, statistics):
    """
    Explain the first refused delete of a folder, once per folder, so the log says
    why the deletes fail instead of only repeating the same error for every file.

    A delete needs write and execute on the folder that HOLDS the file, so the mode
    and the owner of that folder are what matters, the mode of the file itself does
    not decide this.
    """
    folder_path = get_parent_folder(file_path, environment)

    if folder_path in statistics["permission_denied_folders"]:
        return
    statistics["permission_denied_folders"].add(folder_path)

    if environment == ENVIRONMENT_LOCAL:
        logging.error("PERMISSION DENIED on the folder %s : the account running this "
                      "script needs delete rights on the folder itself", folder_path)
        return

    try:
        attributes = get_sftp_handle(session).stat(folder_path)
        logging.error("PERMISSION DENIED on the folder %s : mode=%s owner uid=%s gid=%s. "
                      "A delete needs write and execute on this folder.",
                      folder_path, stat.filemode(attributes.st_mode),
                      attributes.st_uid, attributes.st_gid)
    except Exception as error:
        logging.error("PERMISSION DENIED on the folder %s, its rights could not be read : %s",
                      folder_path, error)
        return

    # the SFTP account owns its own home folder, so its uid and gid can be shown next
    # to the ones of the folder that refuses the delete, which is what has to be compared
    home_folder = get_sftp_home_folder(session)
    try:
        home_attributes = get_sftp_handle(session).stat(home_folder)
        logging.error("The SFTP account owns its home folder %s as uid=%s gid=%s. When "
                      "these do not match the folder above, the folder has to be "
                      "chowned or the cleanup has to run with -env=local instead.",
                      home_folder, home_attributes.st_uid, home_attributes.st_gid)
    except Exception:
        pass


def delete_empty_folder(environment, session, folder_path):
    """Remove one empty folder, returns (True, "") or (False, error_text)."""
    try:
        if environment == ENVIRONMENT_LOCAL:
            os.rmdir(folder_path)
        else:
            get_sftp_handle(session).rmdir(folder_path)
        return True, ""
    except Exception as error:
        return False, str(error)


def delete_empty_folders(environment, session, folder_path, statistics, is_root=False):
    """
    Remove the sub folders that are empty after the cleanup.
    The folder from the configuration file itself is never removed.
    """
    for entry in list_folder(environment, session, folder_path, statistics):
        entry_path, is_folder, is_link = entry[1], entry[2], entry[3]
        if is_folder and not is_link:
            delete_empty_folders(environment, session, entry_path, statistics)

    if is_root:
        return

    if len(list_folder(environment, session, folder_path, statistics)) > 0:
        return

    removed, error_text = delete_empty_folder(environment, session, folder_path)
    if removed:
        statistics["empty_folders_deleted"] = statistics["empty_folders_deleted"] + 1
        logging.info("DELETED EMPTY FOLDER : %s", folder_path)
    else:
        logging.warning("Could not remove empty folder %s : %s", folder_path, error_text)


# ---------------------------------------------------------------------------
# 9. REPORT AND COUNTERS
# ---------------------------------------------------------------------------

def open_deleted_files_report(log_folder, run_stamp, enabled):
    """Open the CSV audit report that lists every deleted file. Returns (file, writer)."""
    if not enabled:
        return None, None

    report_path = os.path.join(log_folder, "sftp_cleanup_deleted_files_%s.csv" % run_stamp)
    report_file = open(report_path, "w", newline="", encoding="utf-8")
    report_writer = csv.writer(report_file)
    report_writer.writerow(["deleted_at", "environment", "file_path",
                            "size_bytes", "last_modified", "status"])

    logging.info("Deleted files report: %s", report_path)
    return report_file, report_writer


def write_report_row(report_writer, environment, file_path, size_bytes,
                     modification_time, status):
    """Add one line to the CSV audit report."""
    if report_writer is None:
        return

    if modification_time:
        last_modified = datetime.fromtimestamp(modification_time).strftime("%Y-%m-%d %H:%M:%S")
    else:
        last_modified = ""

    report_writer.writerow([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        environment,
        file_path,
        size_bytes,
        last_modified,
        status,
    ])


def create_statistics():
    """All counters used for the summary."""
    return {
        "paths_cleaned": 0,
        "paths_not_found": 0,
        "files_scanned": 0,
        "folders_scanned": 0,
        "files_deleted": 0,
        "files_skipped": 0,
        "files_failed": 0,
        "files_permission_denied": 0,
        # the folders that already reported a rights problem, so the explanation is
        # written once per folder and not once per file
        "permission_denied_folders": set(),
        "bytes_deleted": 0,
        "empty_folders_deleted": 0,
        "errors": 0,
        "folder_errors": 0,
    }


# ---------------------------------------------------------------------------
# 10. CLEANUP
# ---------------------------------------------------------------------------

def should_delete_file(modification_time, cutoff_timestamp, age_in_days):
    """
    Decide if a single file has to be deleted.
    Returns (True, "") or (False, reason_text).
    """
    if modification_time is None:
        return False, "no modification time reported"

    if modification_time >= cutoff_timestamp:
        return False, "newer than %d day(s)" % age_in_days

    return True, ""


def clean_one_path(environment, session, path_entry, dry_run, options,
                   statistics, report_writer, report_file):
    """
    Clean one folder from the configuration file.
    The folder is checked first, a missing folder is reported with the
    'running env: <env> not found <path>' error and the run continues with the
    next folder from the configuration file.
    """
    folder_path = path_entry["path"]
    age_in_days = path_entry["age"]
    recurse = path_entry["recurse"]

    logging.info("-" * 70)
    logging.info("Cleaning %s | older than %d day(s) | %s",
                 folder_path, age_in_days,
                 "RECURSIVE" if recurse else "NOT RECURSIVE")

    resolved_path = resolve_cleanup_path(environment, session, folder_path)
    if resolved_path is None:
        log_path_not_found(environment, folder_path)
        log_nearest_existing_parent(environment, session, folder_path)
        statistics["paths_not_found"] = statistics["paths_not_found"] + 1
        return

    folder_path = resolved_path
    cutoff_timestamp = get_cutoff_timestamp(age_in_days)
    logging.info("Deleting the files last changed before %s",
                 datetime.fromtimestamp(cutoff_timestamp).strftime("%Y-%m-%d %H:%M:%S"))

    statistics["paths_cleaned"] = statistics["paths_cleaned"] + 1
    log_every = options["logEveryNFiles"]

    for file_path, file_size, modification_time in iterate_files(environment, session,
                                                                 folder_path, recurse,
                                                                 statistics):
        statistics["files_scanned"] = statistics["files_scanned"] + 1

        delete_it, reason = should_delete_file(modification_time, cutoff_timestamp, age_in_days)

        if not delete_it:
            statistics["files_skipped"] = statistics["files_skipped"] + 1
            logging.debug("SKIPPED : %s (%s)", file_path, reason)
        elif dry_run:
            statistics["files_deleted"] = statistics["files_deleted"] + 1
            statistics["bytes_deleted"] = statistics["bytes_deleted"] + file_size
            logging.info("WOULD DELETE : %s (%s)", file_path, format_size(file_size))
            write_report_row(report_writer, environment, file_path, file_size,
                             modification_time, "DRY_RUN")
        else:
            deleted, error_text = delete_file(environment, session, file_path,
                                              options["retryCount"],
                                              options["retryDelaySeconds"])
            if deleted:
                statistics["files_deleted"] = statistics["files_deleted"] + 1
                statistics["bytes_deleted"] = statistics["bytes_deleted"] + file_size
                logging.info("DELETED : %s (%s)", file_path, format_size(file_size))
                write_report_row(report_writer, environment, file_path, file_size,
                                 modification_time, "DELETED")
            else:
                statistics["files_failed"] = statistics["files_failed"] + 1
                logging.error("FAILED TO DELETE : %s : %s", file_path, error_text)
                write_report_row(report_writer, environment, file_path, file_size,
                                 modification_time, "FAILED: %s" % error_text)
                if is_permission_error(error_text):
                    statistics["files_permission_denied"] = \
                        statistics["files_permission_denied"] + 1
                    log_permission_denied_hint(environment, session, file_path, statistics)

        # progress line and flush of the report, so a long run can be followed live
        if statistics["files_scanned"] % log_every == 0:
            logging.info("PROGRESS : scanned=%d deleted=%d skipped=%d failed=%d freed=%s",
                         statistics["files_scanned"], statistics["files_deleted"],
                         statistics["files_skipped"], statistics["files_failed"],
                         format_size(statistics["bytes_deleted"]))
            if report_file is not None:
                report_file.flush()

    if options["deleteEmptyFolders"] and recurse and not dry_run:
        logging.info("Removing the empty sub folders of %s ...", folder_path)
        delete_empty_folders(environment, session, folder_path, statistics, is_root=True)


def run_cleanup(environment, session, path_entries, dry_run, options, statistics,
                report_writer, report_file):
    """
    Clean every folder listed in the configuration file, one after the other.
    The counters are handed in by the caller instead of being created here, so the
    summary still reports what was already done when the run is cancelled with
    Ctrl+C or stopped by an error in the middle of a folder.
    """
    if dry_run:
        logging.warning("DRY RUN is enabled, no file will actually be deleted")

    for path_entry in path_entries:
        clean_one_path(environment, session, path_entry, dry_run, options,
                       statistics, report_writer, report_file)

    return statistics


# ---------------------------------------------------------------------------
# 11. SUMMARY
# ---------------------------------------------------------------------------

def log_summary(statistics, environment, dry_run, path_entries,
                start_datetime, end_datetime, reconnects):
    """Write the summary statistics at the end of the run."""
    duration = end_datetime - start_datetime
    duration_seconds = duration.total_seconds()

    files_per_second = 0.0
    if duration_seconds > 0:
        files_per_second = statistics["files_scanned"] / duration_seconds

    logging.info("=" * 70)
    logging.info("CLEANUP EXECUTION SUMMARY")
    logging.info("=" * 70)
    logging.info("Running env           : %s%s", environment, " (DRY RUN)" if dry_run else "")
    logging.info("Folders in config     : %d", len(path_entries))
    logging.info("Folders cleaned       : %d", statistics["paths_cleaned"])
    logging.info("Folders not found     : %d", statistics["paths_not_found"])
    logging.info("Folders scanned       : %d", statistics["folders_scanned"])
    logging.info("Files scanned         : %d", statistics["files_scanned"])
    logging.info("Files deleted         : %d", statistics["files_deleted"])
    logging.info("Files skipped         : %d", statistics["files_skipped"])
    logging.info("Files failed          : %d", statistics["files_failed"])
    if statistics["files_permission_denied"] > 0:
        logging.info("  of those, no rights : %d in %d folder(s)",
                     statistics["files_permission_denied"],
                     len(statistics["permission_denied_folders"]))
    logging.info("Empty folders deleted : %d", statistics["empty_folders_deleted"])
    logging.info("Folder read errors    : %d", statistics["folder_errors"])
    logging.info("Other errors          : %d", statistics["errors"])
    if environment == ENVIRONMENT_SFTP:
        logging.info("SFTP reconnects       : %d", reconnects)
    logging.info("Space freed           : %s", format_size(statistics["bytes_deleted"]))
    logging.info("Started               : %s", start_datetime.strftime("%Y-%m-%d %H:%M:%S"))
    logging.info("Ended                 : %s", end_datetime.strftime("%Y-%m-%d %H:%M:%S"))
    logging.info("Duration              : %s", str(duration).split(".")[0])
    logging.info("Throughput            : %.1f file(s)/second", files_per_second)
    logging.info("=" * 70)


def get_exit_code(statistics):
    """0 = clean run, 2 = finished but a folder was missing or a delete failed."""
    if statistics["paths_not_found"] > 0 or statistics["files_failed"] > 0 \
            or statistics["errors"] > 0 or statistics["folder_errors"] > 0:
        return 2
    return 0


# ---------------------------------------------------------------------------
# 12. MAIN
# ---------------------------------------------------------------------------

def main():
    # ---- arguments -------------------------------------------------------
    try:
        arguments = parse_arguments(sys.argv[1:])
    except ValueError as error:
        print("ERROR: %s" % error)
        print("")
        print_usage()
        return 1

    if arguments["show_help"] or len(sys.argv) == 1:
        print_usage()
        return 0

    environment = arguments["environment"]
    dry_run = arguments["dry_run"]
    config_path = arguments["config_path"]

    # ---- configuration ---------------------------------------------------
    sftp_config = None
    try:
        config = load_configuration(config_path)
        sftp_section = get_sftp_section(config)
        options = get_options(config)
        path_entries = get_path_entries(sftp_section, environment,
                                        options["minimumDaysOldAllowed"])

        # the SFTP credentials are only needed, and only checked, when the
        # cleanup runs against the SFTP server
        if environment == ENVIRONMENT_SFTP:
            sftp_config = build_sftp_config(sftp_section)
    except (IOError, OSError, ValueError, json.JSONDecodeError) as error:
        print("ERROR: %s" % error)
        return 1

    # ---- logging ---------------------------------------------------------
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_folder = get_log_folder(options)
    try:
        log_file_path = setup_logging(log_folder, run_stamp)
    except OSError as error:
        print("ERROR: cannot create the log folder %s : %s" % (log_folder, error))
        return 1

    start_datetime = datetime.now()
    logging.info("=" * 70)
    logging.info("ARCHIVE CLEANUP STARTED AT %s", start_datetime.strftime("%Y-%m-%d %H:%M:%S"))
    logging.info("=" * 70)
    log_configuration(environment, dry_run, config_path, log_file_path,
                      sftp_section, path_entries, options)

    session = None
    report_file = None
    statistics = create_statistics()
    exit_code = 0

    try:
        # ---- connect (SFTP only) -----------------------------------------
        if environment == ENVIRONMENT_SFTP:
            session = open_sftp_session(sftp_config)

        # ---- cleanup -----------------------------------------------------
        report_file, report_writer = open_deleted_files_report(
            log_folder, run_stamp, options["writeDeletedFilesReport"])

        run_cleanup(environment, session, path_entries, dry_run,
                    options, statistics, report_writer, report_file)

        exit_code = get_exit_code(statistics)

    except (IOError, OSError) as error:
        logging.error("FATAL ERROR : %s", error)
        exit_code = 1
    except KeyboardInterrupt:
        logging.warning("Run cancelled by the user, reporting what was done so far")
        exit_code = 2
    except Exception as error:
        logging.exception("UNEXPECTED ERROR : %s", error)
        exit_code = 1
    finally:
        if report_file is not None:
            try:
                report_file.close()
            except OSError as error:
                logging.warning("Could not close the report file : %s", error)

        close_sftp_session(session)

        end_datetime = datetime.now()
        log_summary(statistics, environment, dry_run, path_entries,
                    start_datetime, end_datetime,
                    session["reconnects"] if session else 0)
        cleanup_old_log_files(log_folder, options["logRetentionDays"])
        logging.info("ARCHIVE CLEANUP FINISHED AT %s (exit code %d)",
                     end_datetime.strftime("%Y-%m-%d %H:%M:%S"), exit_code)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
