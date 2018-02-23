#
# sqoop - sql query unload
#
# assumes: run from configured EMR
#          sql query --> parquet issue not resolved
#          CONN_PARM file contents: oracle.jdbc.mapDateToTimestamp=false

export ORACLE_URL=jdbc:oracle:thin:@${DB_HOST}:${DB_PORT}

# query to S3 as textfile
sqoop import \
--connection-param-file $CONN_PARM \
--connect $ORACLE_URL/$DB_NAME \
--username $DB_USER \
--password $DB_PASS \
--query $SQL_STMT \
--as-textfile \
--delete-target-dir \
--target-dir $S3_RAW_FILE \
--num-mappers $NUM_MAPPERS

# query to local HDFS as parquetfile
sqoop import \
--connection-param-file $CONN_PARM \
--connect $ORACLE_URL/$DB_NAME \
--username $DB_USER \
--password $DB_PASS \
--table SYS.USER_TABLES \
--as-parquetfile \
--delete-target-dir \
--target-dir $HDFS_LOCAL_FILE \
--num-mappers $NUM_MAPPERS

# then copy to S3 using: hadoop distcp
# NOTE: spark/scala can output a query directly to S3 as parquet
