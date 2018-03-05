## EBS and RDS snapshot management

Primarily aimed at managing a non-clustered, 2-tier application architecture. The rationale for snapshots is to provide a recovery point from which to rebuild a defunct application stack. This approach is not recommended for high reliability, availability, or zero data loss environments.

Due consideration must be given to the namespace being managed. In this respect, AWS tagging is your friend. In the code below, east and west are regions hosting services having the same or similar namespace and tagging.

The CLI create commands have associated latency and are not good Lambda candidates. An alternate approach might be to automate the snapshot creation separately in the live region, then copy those snapshots to a recovery region later.

With an appropriate bash wrapper, the Python script may be run from the EC2 server via crontab. The code given below is nominally Python 2.7 version, but should work with version 3.n as well:  [ebs_rds_snap_mgmt.py](https://github.com/kencarb/perf-coding/blob/master/ebs_rds_snap_mgmt.py)
