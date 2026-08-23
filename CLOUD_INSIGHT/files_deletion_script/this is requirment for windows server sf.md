this is requirment for windows server sftp location and make every operation as seperate function

The current Talend-based cleanup process for the SFTP archive folder is failing due to runtime errors, and file deletion operations are taking longer than expected. To improve reliability and performance, a standalone cleanup script needs to be developed to automatically delete files from the archive folder that are older than a configurable number of days.

The solution must be fully parameterized and driven through configuration files to avoid code changes when updating runtime settings.

Develop a script to delete files from the archive folder based on file age.
Delete files older than N days, where N is configurable.
All configuration values must be externalized into a configuration file.
The script should support recursive and non-recursive deletion modes.
Include logging for:
Script start/end
Files deleted
Files skipped
Errors and exceptions
Summary statistics
Handle large volumes of files efficiently.
Provide proper error handling and recovery mechanisms.
Generate execution logs for audit and troubleshooting purpose

input1 = input n-days, 
input2= -recursive_deletion , -not_recursive_deletion, 

