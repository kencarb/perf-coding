## Clone EC2 Launch Config with new AMI

This method can be run periodically – e.g. via crontab – on a running EC2 instance. For singleton server architecture, this is relatively simple. A more sophisticated scheme will be required for server clusters.

Mapped parameters – as in those resolved at deployment time via a CFT – may need to be stored for later reference. This path was used in a RHEL7 AMI EC2 instance:

```
bin_dir=/usr/local/sbin
env_file=${bin_dir}/lc_env
```

The env_file contains bash entries of the form:

```export env_key=env_value```

The LC clone script simply evaluates the env_file:

```
eval $(grep env_key $env_file)
#etc.
```

The LC clone script then continues to gather metadata from the EC2 instance:

```
inst_id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id/)
az=$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone/)
acct=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document/ | grep accountId | grep -Eo '[[:digit:]]*')
region=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document/ | grep region | cut -f2 -d: | sed 's/[^-[:alnum:]]//g')
AWS_DEFAULT_REGION=${region}
curr_ami=$(curl -s http://169.254.169.254/latest/meta-data/ami-id/)
curr_ami_name=$(aws ec2 describe-images --owners self --filters Name=image-id,Values=${curr_ami} | grep \"Name\": | cut -d\" -f4)
```

The next task is to determine if a new AMI is available. This may be logically determined by querying AMI’s associated with the AWS account. Alternatively – and possibly more decisively – this may be noted in a json document:

```
cd ${bin_dir}
curl -O https://github.com/<your-repo>/rhel7.json
ami_json=${bin_dir}/rhel7.json
python ${bin_dir}/parse_ami.py > ${ami_file}
eval $(cat ${ami_file})
new_ami=${latest_ami_id}
new_ami_name=$(aws ec2 describe-images --image-ids ${new_ami} | grep \"Name\": | cut -d\" -f4)
```

Parsing the AMI from the json depends on a regular format, but an example of parse_ami.py is given as:

```
import json
import os
jfile = os.environ['ami_json']
acct = os.environ['acct']
region = os.environ['region']
with open(jfile, 'r') as infile:
    data = json.load(infile)
for a in data['Accounts']:
    if a['AccountNumber'] == acct:
        print('acct_nm=' + a['AccountName'])
        for r in a['Regions']:
            if r['RegionName'] == region:
                print('latest_ami_id=' + r['LatestAmiId'])
    else:
        continue
```

…admittedly a mash up of bash and python, but it gets the job done. A go/no-go decision may be made, the simplest of which is:

```[[ $curr_ami == $new_ami ]] && exit```

To apply the new_ami, clone the instance userdata and specify the new AMI:

```
new_lc_name=${ec2_name}-lc-${new_ami_name}
aws autoscaling create-launch-configuration --launch-configuration-name $new_lc_name --image-id $new_ami --instance-id $inst_id
```

Update auto scaling group with new LC and verify:

```
asg_query=$(aws ec2 describe-instances --instance-ids $inst_id --query 'Reservations[].Instances[].[Tags[?Key==`aws:autoscaling:groupName`] | [0].Value]')
asg_name=$(echo $asg_query | cut -d\" -f2)
aws autoscaling update-auto-scaling-group --auto-scaling-group-name $asg_name --launch-configuration-name $new_lc_name
lc_query=$(aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names $asg_name --query 'AutoScalingGroups[].LaunchConfigurationName')
lc_query_name=$(echo $lc_query | cut -d\" -f2)
while [[ $lc_query_name != $new_lc_name ]]
do
  sleep 5
  lc_query=$(aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names $asg_name --query 'AutoScalingGroups[].LaunchConfigurationName')
  lc_query_name=$(echo $lc_query | cut -d\" -f2)
done
aws autoscaling delete-launch-configuration --launch-configuration-name $old_lc_name
```

Perform any necessary shutdown, for example EBS detach:

```
vol_state=$(aws ec2 describe-volumes --filters "Name=tag-key,Values=AMI_AUTOMATE" "Name=tag-value,Values=${ec2_name}" --query 'Volumes[].[VolumeId,State]')
vol_id=$(echo $vol_state | cut -d\" -f2)
vol_status=$(echo $vol_state | cut -d\" -f4 | tr '[:upper:]' '[:lower:]')
aws ec2 detach-volume --volume-id $vol_id
# poll the volume to confirm availability / detached
while [[ $vol_status != available ]]
do
  sleep 5
  vol_state=<same as above>
  vol_status=<same as above>
done
```

…and terminate the EC2 instance:

```aws ec2 terminate-instances --instance-ids $inst_id```

The ASG will notice the “unhealthy” instance and fire up a new one using the new LC spec.
