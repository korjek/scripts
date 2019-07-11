#!/usr/bin/python
import time
import datetime
import argparse as ap
from esxi_functions import *

'''
Written by Hristo Malinov, hma@melexis.com

Snapshot tasks: create, restore, delete, list
'''

def vm_list_snapshot(vm, *args):
    print 'VMWare:', vm.name
    if vm.snapshot:
        for el in vm.snapshot.rootSnapshotList:
            print ">>> Snapshot name:", el.name
            print ">>> Created time:", el.createTime
            print ">>> Memory state:", el.state
    else:
        print ">>> No snapshot found!"


def vm_create_snapshot(vm, snapshot_name):
    description = "Creating snapshot {}".format(snapshot_name)
#    dump_memory = True
    dump_memory = False
    quiesce = True
    print '{} for vmware: {}'.format(description, vm.name)
    task = vm.CreateSnapshot(snapshot_name, description, dump_memory, quiesce)
    result = wait_for_task(task, 'VM create snapshot')
    return result


def vm_restore_snapshot(vm, snapshot_name):
    snapshots = vm.snapshot.rootSnapshotList
    for snapshot in snapshots:
        if snapshot_name == snapshot.name:
            snap_obj = snapshot.snapshot
            print "Reverting snapshot ", snapshot.name
            task = snap_obj.RevertToSnapshot_Task()
            result = wait_for_task(task, 'VM revert snapshot')
    return result


def vm_delete_snaphost(vm, snapshot_name):
    snapshots = vm.snapshot.rootSnapshotList
    for snapshot in snapshots:
        if snapshot_name == snapshot.name:
            snap_obj = snapshot.snapshot
            print "Removing snapshot", snapshot.name
            task = snap_obj.RemoveSnapshot_Task(True)
            result = wait_for_task(task, 'VM delete snapshot')
            return result
        else:
            print "Couldn't find snapshot: {}".format(snapshot_name)


def main():
    FUNCTION_MAP = {'list' : vm_list_snapshot,
                    'create' : vm_create_snapshot,
                    'restore' : vm_restore_snapshot,
                    'delete' :vm_delete_snaphost }

    parser = ap.ArgumentParser(description="My Script")
    parser.add_argument('command', choices=FUNCTION_MAP.keys(),
                       help='Snapshot command')
    parser.add_argument('host', help='Hostname to perform snaphost action')
    parser.add_argument('snapshot', nargs='?', 
                       default='snapshot_{}'.format(datetime.date.today()),
                       help='Snapshot name, optional.')
    args = parser.parse_args()
    #print "Snapshot name", args.snapshot
    # Connection to vcenter
    si, content = vcenter_connection()
    #vm = get_obj(content, [vim.VirtualMachine], args.host)
    func = FUNCTION_MAP[args.command]
    vm = get_obj(content, [vim.VirtualMachine], args.host)
    func(vm, args.snapshot)

if __name__ == "__main__":
   main()
