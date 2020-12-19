:: Similar to the rsync plugin, which is written in Bash, this plugin is
:: written as a Windows .bat script. This is a simple test that we can execute
:: non-Python plugins correctly. This one just echoes a given message into a
:: file of a given name.

echo %PERU_MODULE_MESSAGE%> "%PERU_SYNC_DEST%\%PERU_MODULE_FILENAME%"
