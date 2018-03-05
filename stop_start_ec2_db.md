## Stop and Start a server/DB stack

This is somewhat conceptual and might be better accomplished by manipulating CFT stacks directly. However, it does highlight some features available via CLI:

* Manipulating ASG (auto scaling group) parameters
* Ability to stop a running RDS – this appears to also preserve the DB state without having to drop all connections and perform a snapshot

The CLI commands are not blocking, and thus may be implemented via Lambda. The code given below is nominally Python 2.7 version, but should work with version 3.n as well:

```
import os
import boto3
import logging
inst_group = os.environ['INSTANCE_GROUP']
inst_list = os.environ['INSTANCE_LIST'].split(",")
log_level = os.environ['LOG_LEVEL']
my_session = boto3.session.Session()
my_region = my_session.region_name
logger = logging.getLogger()
logger.setLevel(log_level)
asg_cli = boto3.client('autoscaling', region_name=my_region)
rds_cli = boto3.client('rds', region_name=my_region)
```

The stop / start functions are given:

```
def asg_stop_inst():
    paginator = asg_cli.get_paginator('describe_auto_scaling_groups')
    page_iterator = paginator.paginate(
        PaginationConfig={'PageSize': 100}
    )
    filtered_asgs = page_iterator.search(
        'AutoScalingGroups[] | [?contains(Tags[?Key==`{}`].Value, `{}`)]'.format(
            'INSTANCE_GROUP', inst_group
        )
    )
    for asg in filtered_asgs:
        asg_nm = asg['AutoScalingGroupName']
        resp = asg_cli.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_nm])
        for asg in resp['AutoScalingGroups']:
            for tag in asg['Tags']:
                tag_key = tag['Key']
                tag_val = tag['Value']
                if tag_key == 'Name' and tag_val in inst_list:
                    logger.info('stopping ASG : ' + asg_nm + " - " + tag_val)
                    resp = asg_cli.update_auto_scaling_group(AutoScalingGroupName=asg_nm, DesiredCapacity=0)
                    logger.info(resp)
    return 0
    
def rds_stop_inst():
    paginator = rds_cli.get_paginator('describe_db_instances')
    page_iterator = paginator.paginate(
        Filters=[
            {
                'Name': 'db-instance-id',
                'Values': inst_list
            },
        ],
        PaginationConfig={'PageSize': 100}
    )
    for dbs in page_iterator:
        for db in dbs['DBInstances']:
            if db:
                db_inst_id = db['DBInstanceIdentifier']
                db_status = db['DBInstanceStatus']
                if db_status == 'available':
                    logger.info('stopping RDS : ' + db_inst_id + " - " + db_status)
                    resp = rds_cli.stop_db_instance(DBInstanceIdentifier=db_inst_id)
                    logger.info(resp)
                else:
                    logger.info('ignoring RDS : ' + db_inst_id + " - " + db_status)
    return 0

def asg_start_inst():
    paginator = asg_cli.get_paginator('describe_auto_scaling_groups')
    page_iterator = paginator.paginate(
        PaginationConfig={'PageSize': 100}
    )
    filtered_asgs = page_iterator.search(
        'AutoScalingGroups[] | [?contains(Tags[?Key==`{}`].Value, `{}`)]'.format(
            'INSTANCE_GROUP', inst_group
        )
    )
    for asg in filtered_asgs:
        asg_nm = asg['AutoScalingGroupName']
        resp = asg_cli.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_nm])
        for asg in resp['AutoScalingGroups']:
            for tag in asg['Tags']:
                tag_key = tag['Key']
                tag_val = tag['Value']
                if tag_key == 'Name' and tag_val in inst_list:
                    logger.info('starting ASG : ' + asg_nm + " - " + tag_val)
                    resp = asg_cli.update_auto_scaling_group(AutoScalingGroupName=asg_nm, DesiredCapacity=1)
                    logger.info(resp)
    return 0
    
def rds_start_inst():
    paginator = rds_cli.get_paginator('describe_db_instances')
    page_iterator = paginator.paginate(
        Filters=[
            {
                'Name': 'db-instance-id',
                'Values': inst_list
            },
        ],
        PaginationConfig={'PageSize': 100}
    )
    for dbs in page_iterator:
        for db in dbs['DBInstances']:
            if db:
                db_inst_id = db['DBInstanceIdentifier']
                db_status = db['DBInstanceStatus']
                if db_status == 'stopped':
                    logger.info('starting RDS : ' + db_inst_id + " - " + db_status)
                    resp = rds_cli.start_db_instance(DBInstanceIdentifier=db_inst_id)
                    logger.info(resp)
                else:
                    logger.info('ignoring RDS : ' + db_inst_id + " - " + db_status)
    return 0
```

The Lamdba entry point then calls the desired function(s):

```
def lambda_handler(event, context):
    logger.info('INSTANCE_GROUP : ' + inst_group)
    logger.info('INSTANCE_LIST : ' + str(inst_list))
    logger.info('REGION : ' + my_region)
    asg_rc = asg_stop_inst()
    #asg_rc = asg_start_inst()
    logger.info('ASG func rc : ' + str(asg_rc))
    rds_rc = rds_stop_inst()
    #rds_rc = rds_start_inst()
    logger.info('RDS func rc : ' + str(rds_rc))
    return 0
```
