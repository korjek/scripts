#!/usr/bin/python

'''
Updates the maximum number of NFS datastores

'''
import sys
from esxi_functions import *

if len(sys.argv) < 2:
    print 'Run the script as {} 64L'.format(sys.argv[0])
    print 'Where 64L is the new value for maximum number of NFS datastores'
    sys.exit(1)
else:
    ds_value = long(sys.argv[1])

# Establish connection to vCenter
si, content = vcenter_connection()
# Get all hosts objects
esxi_hosts = get_hosts(si)

for host in esxi_hosts:
    try:
        advanced_options = host.configManager.advancedOption
        nfs_max_vols = advanced_options.QueryOptions('NFS.MaxVolumes')
        print '{}, current NFS.MaxVolumes: {}'.format(host.name, nfs_max_vols[0].value)
        nfs_max_vols[0].value = ds_value
        advanced_options.UpdateOptions(nfs_max_vols)
        nfs_max_vols_value = host.configManager.advancedOption.QueryOptions('NFS.MaxVolumes')[0].value
        print '{}, updated NFS.MaxVolumes: {}'.format(host.name, nfs_max_vols_value)
    except Exception as e:
        print e

