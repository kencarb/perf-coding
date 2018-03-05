from datetime import datetime
from datetime import timedelta
import os
import json
import time
import boto3
import logging

# initialize shell environment variables...
inst_nm = os.environ['instance_nm']
logging.basicConfig(
    filename=os.environ['log_file_path'],
    level=logging.os.environ['logging_level'].upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(inst_nm)
retention_days = timedelta(days=int(os.environ['retention_days']))
tgt_ebs_key = os.environ['target_EBS_encrypt_arn']
tgt_rds_key = os.environ['target_RDS_encrypt_arn']
src_region = os.environ['source_region']
INSTANCE_GROUP =  os.environ['INSTANCE_GROUP']
ENV_LEVEL =  os.environ['ENV_LEVEL']
APP_OWNER =  os.environ['APP_OWNER']
APP_TOPIC_ARN =  os.environ['APP_TOPIC_ARN']

if src_region != 'us-east-1' and src_region != 'us-west-2':
    src_region = 'us-east-1'

if src_region == 'us-east-1':
    src_rds_client = boto3.client('rds', region_name='us-east-1')
    src_ec2_client = boto3.client('ec2', region_name='us-east-1')
    tgt_rds_client = boto3.client('rds', region_name='us-west-2')
    tgt_ec2_client = boto3.client('ec2', region_name='us-west-2')
else:    
    src_rds_client = boto3.client('rds', region_name='us-west-2')
    src_ec2_client = boto3.client('ec2', region_name='us-west-2')
    tgt_rds_client = boto3.client('rds', region_name='us-east-1')
    tgt_ec2_client = boto3.client('ec2', region_name='us-east-1')

sns_client = boto3.client('sns')

snapshot_name = inst_nm + '-save-' + time.strftime("%Y%m%d")
snapshot_search = inst_nm + '-save-*'
y_flg = 'Y'
n_flg = 'N'
today = datetime.strptime(time.strftime("%Y-%m-%d"), '%Y-%m-%d').date()
delete_date = today - retention_days 
message = 'RDS and EBS manual snapshots via Lambda: ' + snapshot_name + ': ' + time.strftime("%Y-%m-%d %H:%M:%S")

def inform_message(f_msg):
    global message
    logger.info(f_msg)
    message = message + "\n" + f_msg
    return
    
def send_sns_message():
    sns_client.publish(
        TopicArn=APP_TOPIC_ARN,
        Message=message
    )
    return

def tag_ebs_snapshot_source(f_snap_id):
    logger.info('in tag_ebs_snapshot_source')
    resp = src_ec2_client.create_tags(
        Resources=[f_snap_id,],
        Tags=[
            {'Key': 'INSTANCE_GROUP','Value': INSTANCE_GROUP},
            {'Key': 'ENV_LEVEL','Value': ENV_LEVEL},
            {'Key': 'APP_OWNER','Value': APP_OWNER},
            {'Key': 'Name','Value': snapshot_name}
        ]
    )
    rstr = json.dumps(resp, default=str)
    logger.debug('create_tags status: ' + rstr)
    return

def tag_ebs_snapshot_target(f_snap_id):
    logger.info('in tag_ebs_snapshot_target')
    resp = tgt_ec2_client.create_tags(
        Resources=[f_snap_id,],
        Tags=[
            {'Key': 'INSTANCE_GROUP','Value': INSTANCE_GROUP},
            {'Key': 'ENV_LEVEL','Value': ENV_LEVEL},
            {'Key': 'APP_OWNER','Value': APP_OWNER},
            {'Key': 'Name','Value': snapshot_name}
        ]
    )
    rstr = json.dumps(resp, default=str)
    logger.debug('create_tags status: ' + rstr)
    return
    
def find_rds_snapshot_source(f_snap_nm):
    logger.info('in find_rds_snapshot_source')
    try:
        resp = src_rds_client.describe_db_snapshots(
            DBSnapshotIdentifier=f_snap_nm
        )
    except Exception as error:
        logger.debug('{}'.format(error))
        logger.debug('assuming RDS snap ' + f_snap_nm + ' not found')
        return n_flg
    return y_flg

def find_ebs_snapshot_source(f_snap_nm):
    logger.info('in find_ebs_snapshot_source')
    resp = src_ec2_client.describe_snapshots(
        Filters=[
            {'Name':'tag-key','Values':['Name']},
            {'Name':'tag-value','Values':[f_snap_nm]}
        ]
    )
    rstr = json.dumps(resp, default=str)
    rdict = json.loads(rstr)
    logger.debug(rdict['Snapshots'])
    if rdict['Snapshots']:
        return y_flg
    else:
        return n_flg

def create_rds_snapshot_source(f_snap_nm):
    logger.info('in create_rds_snapshot_source')
    resp = src_rds_client.create_db_snapshot(
        DBSnapshotIdentifier=f_snap_nm,
        DBInstanceIdentifier=inst_nm
    )
    rstr = json.dumps(resp, default=str)
    logger.debug('create_db_snapshot response: ' + rstr)
    copy_rds_snaphot_target(snapshot_name)
    return

def create_ebs_snapshot_source(f_snap_nm):
    logger.info('in create_ebs_snapshot_source')
    # finds volume based on tag "SNAP_AUTOMATE" == instance_nm
    resp = src_ec2_client.describe_volumes(
        Filters=[
            {'Name':'tag-key','Values':['SNAP_AUTOMATE']},
            {'Name':'tag-value','Values':[inst_nm]}
        ]
    )
    for v in resp['Volumes']:
        vol_id = v['VolumeId']
        inform_message('EC2 volume ID is ' + vol_id)
        desc = 'snap of volume having tag SNAP_AUTOMATE=' + inst_nm
        resp = src_ec2_client.create_snapshot(
            VolumeId=vol_id,
            Description=desc
        )
        rstr = json.dumps(resp, default=str)
        rdict = json.loads(rstr)
        snap_id = rdict['SnapshotId']
        inform_message('EBS snap ID is ' + snap_id)
        tag_ebs_snapshot_source(snap_id)
        copy_ebs_snapshot_target(snap_id)
    return

def copy_rds_snaphot_target(f_snap_nm):
    logger.info('in copy_rds_snaphot_target - argv = ' + f_snap_nm)
    while True:
        resp = src_rds_client.describe_db_snapshots(DBSnapshotIdentifier=f_snap_nm)
        rstr = json.dumps(resp, default=str)
        rdict = json.loads(rstr)
        status = rdict['DBSnapshots'][0]['Status']
        if status == 'available':
            break
        time.sleep(30)
    src_arn = rdict['DBSnapshots'][0]['DBSnapshotArn']
    resp = tgt_rds_client.copy_db_snapshot(
        SourceDBSnapshotIdentifier=src_arn,
        TargetDBSnapshotIdentifier=f_snap_nm,
        Tags=[
            {'Key': 'INSTANCE_GROUP','Value': INSTANCE_GROUP},
            {'Key': 'ENV_LEVEL','Value': ENV_LEVEL},
            {'Key': 'APP_OWNER','Value': APP_OWNER}
        ],
        KmsKeyId=tgt_rds_key,
        SourceRegion=src_region
    )
    rstr = json.dumps(resp, default=str)
    rdict = json.loads(rstr)
    tgt_arn = (rdict['DBSnapshot'])['DBSnapshotArn']
    inform_message('RDS snap ARN is: ' + tgt_arn )
    return

def copy_ebs_snapshot_target(f_snap_id):
    logger.info('in copy_ebs_snapshot_target')
    while True:
        resp = src_ec2_client.describe_snapshots(SnapshotIds=[f_snap_id])
        rstr = json.dumps(resp, default=str)
        rdict = json.loads(rstr)
        status = rdict['Snapshots'][0]['State']
        if status == 'completed':
            break
        time.sleep(30)
    desc = 'copy of ' + snapshot_name + ' in ' + src_region
    resp = tgt_ec2_client.copy_snapshot(
        SourceRegion=src_region,
        SourceSnapshotId=f_snap_id,
        Description=desc,
        Encrypted=True,
        KmsKeyId=tgt_ebs_key
    )
    rstr = json.dumps(resp, default=str)
    rdict = json.loads(rstr)
    snap_id = rdict['SnapshotId']
    tag_ebs_snapshot_target(snap_id)
    return

def purge_rds_snaphot():
    logger.info('in purge_rds_snaphot')
    # delete assumes old snapshots are "available"
    src_resp = src_rds_client.describe_db_snapshots(DBInstanceIdentifier=inst_nm,SnapshotType='manual')
    for r in src_resp['DBSnapshots']:
        snap_id = r['DBSnapshotIdentifier']
        cret_tm = json.dumps(r['SnapshotCreateTime'], default=str)
        cret_dt = datetime.strptime(cret_tm.split('"', 2)[1].split(' ', 1)[0], '%Y-%m-%d').date()
        if create_date < delete_date:
            logger.debug('deleting ' + snap_id)
            resp = src_rds_client.delete_db_snapshot(DBSnapshotIdentifier=snap_id)
            rstr = json.dumps(resp, default=str)
            logger.debug('response: ' + rstr)
    tgt_resp = tgt_rds_client.describe_db_snapshots(DBInstanceIdentifier=inst_nm,SnapshotType='manual')
    for r in tgt_resp['DBSnapshots']:
        snap_id = r['DBSnapshotIdentifier']
        cret_tm = json.dumps(r['SnapshotCreateTime'], default=str)
        create_date = datetime.strptime(cret_tm.split('"', 2)[1].split(' ', 1)[0], '%Y-%m-%d').date()
        if create_date < delete_date:
            logger.debug('deleting ' + snap_id)
            resp = tgt_rds_client.delete_db_snapshot(DBSnapshotIdentifier=snap_id)
            rstr = json.dumps(resp, default=str)
            logger.debug('response: ' + rstr)
    return

def purge_ebs_snapshot():
    logger.info('in purge_ebs_snapshot')
    resp = src_ec2_client.describe_snapshots(Filters=[{'Name':'tag-key','Values':['Name']},{'Name':'tag-value','Values':[snapshot_search]}])
    for r in resp['Snapshots']:
        snap_id = r['SnapshotId']
        cret_tm = json.dumps(r['StartTime'], default=str)
        create_date = datetime.strptime(cret_tm.split('"', 2)[1].split(' ', 1)[0], '%Y-%m-%d').date()
        if create_date < delete_date:
            logger.debug('deleting ' + snap_id)
            resp = src_ec2_client.delete_snapshot(SnapshotId=snap_id)
            rstr = json.dumps(resp, default=str)
            logger.debug('response: ' + rstr)
    resp = tgt_ec2_client.describe_snapshots(Filters=[{'Name':'tag-key','Values':['Name']},{'Name':'tag-value','Values':[snapshot_search]}])
    for r in resp['Snapshots']:
        snap_id = r['SnapshotId']
        cret_tm = json.dumps(r['StartTime'], default=str)
        create_date = datetime.strptime(cret_tm.split('"', 2)[1].split(' ', 1)[0], '%Y-%m-%d').date()
        if create_date < delete_date:
            logger.debug('deleting ' + snap_id)
            resp = tst_ec2_client.delete_snapshot(SnapshotId=snap_id)
            rstr = json.dumps(resp, default=str)
            logger.debug('response: ' + rstr)
    return
    
# main entry point...    
#def lambda_handler(event, context):
def main():
    logger.info('snapshot_name:' + snapshot_name)
    logger.info('snapshot_search:' + snapshot_search)
    logger.info('today:' + str(today))
    logger.info('delete_date:' + str(delete_date))
    rrc = 0
    erc = 0
    # RDS snapshot:
    rds_snaps = find_rds_snapshot_source(snapshot_name)
    if rds_snaps == n_flg:
        inform_message('create RDS snap ' + snapshot_name)
        # run create & copy - tags should be inherited
        create_rds_snapshot_source(snapshot_name)
        purge_rds_snaphot()
    else:
        inform_message('RDS snap ' + snapshot_name + ' already exists')
        rrc = 2
    # EBS snapshot:
    ebs_snaps = find_ebs_snapshot_source(snapshot_name)
    if ebs_snaps == n_flg:
        inform_message('create EBS snap ' + snapshot_name)
        # run create+tag & copy+tag processes
        create_ebs_snapshot_source(snapshot_name)
        purge_ebs_snapshot()
    else:
        inform_message('EBS snap ' + snapshot_name + ' already exists')
        erc = 2
    # Send status:
    send_sns_message()
    rc = rrc + erc
    return rc

if __name__ == "__main__":
    main()
