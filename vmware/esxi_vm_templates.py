#!/usr/bin/python

import random

from pyVmomi import vim

from esxi_functions import get_all_objs
from esxi_functions import get_hosts
from esxi_functions import vcenter_connection

'''
Lists all vcenter registered vmware templates

'''

si, content = vcenter_connection()
esxi_hosts = get_hosts(si)
print "-----------------------------------------------"
for host in esxi_hosts:
    for vm in host.vm:
        if vm.config.template == True:
            print "Name:         ", vm.name
            print "Datastore:    ", vm.datastore[0].name
            print "Host name:    ", host.name
            print "Cluster:      ", host.parent.name
            print "Datacenter:   ", host.parent.parent.parent.name
            print "-----------------------------------------------"
