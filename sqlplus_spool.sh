#
# sqlplus - generic bash extract
#
# assumes:  sqlplus installed, available
#           SQL_STMT tailored for output (e.g. concat columns)
#           exec from parent script exporting env params

sqlplus -s "${DB_USER}/${DB_PASS}@(DESCRIPTION=(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP)(HOST=${DB_HOST})(PORT=${DB_PORT})))(CONNECT_DATA=(SERVER=DEDICATED)(SERVICE_NAME=${DB_NAME})))" <<EOF
set echo off
set pagesize 0
set trimspool on
set linesize 1000
set termout off
spool ${SPOOL_FILE}
${SQL_STMT}
spool off
exit
EOF
