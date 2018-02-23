#
# spark query oracle
#
# assumes: run from configured EMR
#          exec from parent script exporting env params

val dbPass = sys.env("DB_PASS")
val dbHost = sys.env("DB_HOST")
val dbPort = sys.env("DB_PORT")
val dbName = sys.env("DB_NAME")
val dbUser = sys.env("DB_USER")
val sqlFile = sys.env("SQL_FILE")
val jdbcUrl = "jdbc:oracle:thin://@" + dbHost + ":" + dbPort + "/" + dbName

# foo is dummy alias - query treated like table
val sqlStmt = "(" + scala.io.Source.fromFile(sqlFile).mkString + ") foo"

# initialize the data frame - appears similar to creating a cursor
val jdbcDF = spark.read.format("jdbc").option("driver", "oracle.jdbc.driver.OracleDriver").option("url", jdbcUrl).option("dbtable", sqlStmt).option("user", dbUser).option"password", dbPass).load()

# fetch query results, write to S3
jdbcDF.write.parquet("s3a://<key>/<obj>")

# do something with the parquet obj
val dfs = spark.read.parquet("s3a://<key>/<obj>")
dfs.count()
dfs.printSchema()
dfs.first()
dfs.repartition(1).write.option("header", "true").mode("overwrite").csv("s3a://<key>/<obj>.csv")

# NOTE - the csv is HDFS type object, however repartition coalesces data into a single partition which may be copied or moved

