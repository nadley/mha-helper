# (c) 2017, Nahir Mohamed <nahir.mohamed@gmail.com>
#
# This file is part of mha_helper
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function
from ssh_helper import SSHHelper
from config_helper import ConfigHelper
import boto3
from botocore.exceptions import ClientError
import re


class EIPAwsHelper(object):
    def __init__(self, host, host_ip=None, ssh_user=None, ssh_port=None, ssh_options=None):
        config_helper = ConfigHelper(host)
        self._aws_instance_id = config_helper.get_aws_instance_id()
        self._aws_instance_network_interface_id = config_helper.get_aws_instance_network_interface_id()
        self._aws_access_key_id = config_helper.get_aws_access_key_id()
        self._aws_secret_access_key = config_helper.get_aws_secret_access_key()
        self._aws_region = config_helper.get_aws_region()
        self._writer_vip_cidr = config_helper.get_writer_vip_cidr()
        self._writer_vip = config_helper.get_writer_vip()
        self._requires_sudo = config_helper.get_requires_sudo()

        self._ssh_client = SSHHelper(host, host_ip, ssh_user, ssh_port, ssh_options)

    def assign_eip(self):
        """
        Use to assign EC2 Elastic IP on the new master
        This use boto3 API for AWS
        :return: boolean
        """

        # Create client to access AWS API
        client = boto3.client('ec2',
                              aws_access_key_id=self._aws_access_key_id,
                              aws_secret_access_key=self._aws_secret_access_key,
                              region_name=self._aws_region)

        try:
            # Check if network interface id is attached to the instance
            network_interfaces = client.describe_network_interfaces(
                Filters=[{'Name': 'attachment.instance-id', 'Values': [self._aws_instance_id, ]},
                         {'Name': 'network-interface-id', 'Values': [self._aws_instance_network_interface_id]}]
            )

            if 'NetworkInterfaces' in network_interfaces and network_interfaces['NetworkInterfaces']:
                print('Interface found %s for instance %s aborting. ' % (self._aws_instance_network_interface_id,
                                                                                          self._aws_instance_id))
            else:
                print('Can\'t found network interface %s for instance %s aborting. ' % (self._aws_instance_network_interface_id,
                                                                                          self._aws_instance_id))
                return False

            # Check if EIP is already assigned to this instance to avoid unwanted fees see warning here :
            # https://boto3.readthedocs.io/en/latest/reference/services/ec2.html#EC2.Client.associate_address
            addresses = client.describe_addresses()

            if 'Addresses' in addresses and addresses['Addresses']:
                for eip in addresses['Addresses']:
                    if eip['PublicIp'] == self._writer_vip:
                        if 'InstanceId' in eip:
                            if eip['InstanceId'] == self._aws_instance_id:
                                print('Instance EC2 with id : %s is already attach to elastic IP %s nothing to do' % (
                                    self._aws_instance_id,
                                    self._writer_vip))
                                return True
                            else:
                                print('Elastic IP %s already in used, going to move it to instance : %s' % (
                                self._writer_vip,
                                self._aws_instance_id))
                                break
                        else:
                            print('Elastic IP %s is not used, going to attach it to instance : %s' % (self._writer_vip,
                                                                                                        self._aws_instance_id))
                            break
            else:
                print('Can\'t found Elastic IP %s in EC2 region %s aborting. ' % (self._writer_vip, self._aws_region))
                return False

            # Attach the Elastic IP to the interface of the instance
            eip_association = client.associate_address(AllocationId=eip['AllocationId'],
                                                NetworkInterfaceId=self._aws_instance_network_interface_id,
                                                AllowReassociation=True)
            if 'AssociationId' in eip_association:
                print ('Elastic IP %s has been associated with instance %s' % (self._writer_vip,
                                                                                   self._aws_instance_id))
                return True
            else:
                print('Something goes wrong during EIP association with instance ')
                return False

        except ClientError as e:
            print("Unexpected error: %s" % e)

    def has_eip(self):
        # Create client to access AWS API
        client = boto3.client('ec2',
                              aws_access_key_id=self._aws_access_key_id,
                              aws_secret_access_key=self._aws_secret_access_key,
                              region_name=self._aws_region)

        addresses = client.describe_addresses()

        if 'Addresses' in addresses and addresses['Addresses']:
            for eip in addresses['Addresses']:
                if eip['PublicIp'] == self._writer_vip:
                    if 'InstanceId' in eip:
                        if eip['InstanceId'] == self._aws_instance_id:
                            print('Instance EC2 with id : %s is already attach to elastic IP %s nothing to do' % (
                                self._aws_instance_id,
                                self._writer_vip))
                            return True
                    else:
                        print('Elastic IP %s is not attach to this instance %s' % (self._writer_vip,
                                                                                   self._aws_instance_id))
                        return False
        else:
            print('Can\'t found Elastic IP %s in EC2 region %s aborting. ' % (self._writer_vip, self._aws_region))
            return False
