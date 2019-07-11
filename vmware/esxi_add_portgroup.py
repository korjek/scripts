#!/usr/bin/python
"""
Add new Port Group to evry ESxi host in Datacenter
"""
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import ConfigParser
import atexit
import time

class bcolors:
    RED = '\033[31m'
    GREEN = '\033[92m'
    ENDC = '\033[0m'

def config_parser(config_file, section):
    """
    Function that returns dict from parsed file and section
    """
    config = ConfigParser.ConfigParser()
    if config.read(config_file):
        data = dict(config.items(section))
        return data
    return None

def vcenter_connection():
    """
    Create a connection to vCenter
    -> returns the ServiceInstance object
    """
    config = "/etc/esxi/config.properties"
    vcenter_conf = config_parser(config, 'VCENTER')
    host = vcenter_conf['host']
    user = vcenter_conf['user']
    pwd = vcenter_conf['pwd']

    try:
        si = SmartConnect(host=host,
                               user=user,
                               pwd=pwd)
    except Exception as e:
            print("Error: ", e)
            raise SystemExit
    atexit.register(Disconnect, si)
    return si

def wait_for_task(task, action_name='job'):
    """
    Waits and provides updates on a vSphere task
    """
    print('Waiting for {} to complete.'.format(action_name))
    while task.info.state == vim.TaskInfo.State.running:
        print('progress: {}% ...'.format(task.info.progress))
        time.sleep(3)

    if task.info.state == vim.TaskInfo.State.success:
        out = 'Task of %s completed successfully.' % task.info.entityName
        out = bcolors.GREEN + out + bcolors.ENDC
        task_result = 1
        print(out)
    else:
        out = 'Task of %s DID NOT complete successfully: %s.' % (task.info.entityName, task.info.error)
        out = bcolors.RED + out + bcolors.ENDC
        task_result = 0
        print(out)

    return migration_result

def get_hosts_in_datacenter(si, datacenter):
    hosts = list()
    content = si.RetrieveContent()
    for child in content.rootFolder.childEntity:
        if (child.name == datacenter):
            dc = child
            cls = dc.hostFolder.childEntity
            for cl in cls:
                hss = cl.host
                for hs in hss:
                    if (hs.summary.config.name == "hulk-tess.tess.elex.be"):
                        hosts.append(hs)
    return hosts

def create_port_group(host, vswitch_name, port_group_name, port_group_vlan_id):
    port_group_spec = vim.host.PortGroup.Specification()
    port_group_spec.name = port_group_name
    port_group_spec.vlanID = port_group_vlan_id
    port_group_spec.vswitchName = vswitch_name
    host.configManager.networkSystem.AddPortGroup(portgrp=port_group_spec)


def main():
    dc = '@option.DATACENTER@' 
    vlan_id = '@option.VLANID@'
    vlan_name = '@option.VLANNAME@'
    failed_hosts = list()
    vswitch = 'vSwitch0'

    si = None
    si = vcenter_connection()
    content = si.RetrieveContent()

    for host in get_hosts_in_datacenter(si, dc):
        print(host)
#        port_group_spec = vim.host.PortGroup.Specification()
#        port_group_spec.name = port_group_name
#        port_group_spec.vlanID = port_group_vlan_id
#        port_group_spec.vswitchName = vswitch_name
#        task = host.configManager.networkSystem.AddPortGroup(portgrp=port_group_spec)
#        description = "\"Creating VLAN\""
#        task_result = wait_for_task(task, description)
#        if task_result != 1:
#            failed_hosts.append(host)

    print("\n VLAN Creationg FAILED for hosts:")
        for host in failde_hosts:
            print(host)

# Start program
if __name__ == "__main__":
    main()




