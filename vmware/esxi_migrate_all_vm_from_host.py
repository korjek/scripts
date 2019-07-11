#!/usr/bin/python
"""
Migrate all VMs from host to other hosts inside the same datacenter and cluster
"""
import sys
from collections import OrderedDict
from esxi_functions import *

class bcolors:
    RED = '\033[31m'
    GREEN = '\033[92m'
    ENDC = '\033[0m'

migratedVms = []
failedMigrateVms = []

esxi_host = sys.argv[1]
cluster = "PROD"

dc = get_datacenter(esxi_host)

si = None
si = vcenter_connection()
content = si.RetrieveContent()
vmsToBeMigrated = OrderedDict(sorted(get_vm_with_mem_size(si, dc, cluster, esxi_host).items(), key=lambda(k,v):(v[1]), reverse=True))
print("Virtual Machines to be migrated")
for data in vmsToBeMigrated.itervalues():
    print(data[0])
print("\n")
for vm, data in vmsToBeMigrated.iteritems():
    task_result = None
    targetHost, targetHostMem = get_host_with_highest_free_mem(si, dc, cluster, esxi_host)
    if (data[1] < targetHostMem):
        relocate_spec = vim.vm.RelocateSpec(host=targetHost)
        task = vm.Relocate(relocate_spec)
        description = "\"Migrating " + data[0] + "\""
        task_result = wait_for_task(task, description)
        if task_result == 1:
            migratedVms.append(data[0])
        else:
            failedMigrateVms.append(data[0])
    else:
        print("No hosts with sufficient free RAM left")

print("\nMigrated VMs:")
for vm in migratedVms:
    print(vm)
print("\n" + bcolors.RED + "Non-migrated VMs:" + bcolors.ENDC)
for vm in failedMigrateVms:
    print(bcolors.RED + vm + bcolors.ENDC)

