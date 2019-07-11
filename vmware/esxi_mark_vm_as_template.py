#!/usr/bin/python

from __future__ import print_function
import os
import sys
from pyVmomi import vim

from esxi_functions import *
from esxi_functions import get_hosts
from esxi_functions import vcenter_connection

'''
Mark as template all VMs with certain name

'''

if len(sys.argv) < 1:
    print('Run the script as {} <datacenter>/vm/<ovf-deployed-name>'.format(sys.argv[0]))
    print('Where <ovf-deployed-name> is the name of the OVF package and <datacenter> is')
    print('\nex: {} /colo.elex.be/vm/rhel74_packer.v1'.format(sys.argv[0]))
    sys.exit(1)
else:
    ovf_template = sys.argv[1]

try:
    host = os.environ['VCENTER_HOST']
    user = os.environ['VCENTER_USER']
    pwd = os.environ['VCENTER_PWD']
    si, content = vcenter_connection(host,user,pwd)
except Exception as e:
    print('There are no environment variables specified.', e)
    print('Continuing with config file.')
    si, content = vcenter_connection()

search_index = si.content.searchIndex

try:
    vm = search_index.FindByInventoryPath(ovf_template)
    if not vm.config.template:
        try:
            print('>>> Converting {}/{} to template'.format(vm.parent.parent.name, vm.name))
            vm.MarkAsTemplate()
        except Exception as e:
            print("ERROR:{}/{} :{}".format(vm.parent.parent.name, vm.name, e))
    else:
        print('# Already marked as template: {}/{}'.format(vm.parent.parent.name, vm.name))
except Exception as e:
    print('Error: VM {} not found'.format(ovf_template))


