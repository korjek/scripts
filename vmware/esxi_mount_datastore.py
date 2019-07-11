#!/usr/bin/python

'''
Mounts NFS datastore on all host of a datastore

'''
import sys
from optparse import OptionParser
from esxi_functions import *


parser = OptionParser()
parser.add_option("--name", help="""Volume name ex. vm_images""")
parser.add_option("--path", help="""Volume export path, ex. /vol/ or /""")
parser.add_option( "--datacenter", help="""Datacenter name, ex. colo.elex.be""")
parser.add_option("--nfsserver", help="""NFS server name, ex. netappvs1.colo.elex.be""")

(options, args) = parser.parse_args()

vol_name = options.name
vol_path = options.path
datacenter = options.datacenter
nfsserver = options.nfsserver

if datacenter not in nfsserver:
    print "ERROR: NFS server should be with the same domain as the datacenter"
    sts.exit(1)

# Establish connection to vCenter
si, content = vcenter_connection()
# Get datacenter object
dc = get_obj(content, [vim.Datacenter], datacenter)

for cluster in dc.hostFolder.childEntity:
    if cluster.name == 'PROD':
        for host in cluster.host:
            try:
                print 'Mounting {} on {} from {}'.format(vol_name, host.name, nfsserver)
                spec = vim.host.NasVolume.Specification()
                spec.remoteHost = nfsserver
                spec.remotePath = vol_path
                spec.localPath = vol_name
                spec.accessMode = "readWrite"
                r = host.configManager.datastoreSystem.CreateNasDatastore(spec)
                print 'Status: {}'.format(r.overallStatus)
            except Exception as e:
                print "Error:", e
