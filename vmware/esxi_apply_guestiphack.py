#!/usr/bin/python

from __future__ import print_function
import os
import sys
from pyVmomi import vim

from esxi_functions import *
from esxi_functions import get_hosts
from esxi_functions import vcenter_connection


if len(sys.argv) < 1:
    print('Run the script as {} <host>'.format(sys.argv[0]))
    print('\nex: {} vmhost22.colo.elex.be'.format(sys.argv[0]))
    sys.exit(1)
else:
    hostname = sys.argv[1]

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
datacenter = '.'.join(hostname.split('.')[1:])

try:
    host = search_index.FindByInventoryPath('/{}/host/PROD/{}'.format(datacenter, hostname))
    option_manager = host.configManager.advancedOption
    if option_manager.QueryOptions("Net.GuestIPHack")[0].value != 1:
        try:
            option = vim.option.OptionValue(key = "Net.GuestIPHack", value=long(1))
            option_manager.UpdateOptions(changedValue=[option])
            print('Set Net.GuestIPHack to 1 for host:{}'.format(host.name))
        except Exception as e:
            print('Error applying Net.GuestIPHack {}'.format(e))
    else:
        print(" Net.GuestIPHack already set to 1 for {}".format(host.name))
except Exception as e:
    print('Error with {}: {}'.format(hostname, e))

