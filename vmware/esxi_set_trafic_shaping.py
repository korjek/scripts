#!/usr/bin/python
from pyVim.connect import SmartConnectNoSSL, Disconnect
from pyVmomi import vim
import ConfigParser
import time
import atexit

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
        si = SmartConnectNoSSL(host=host,
                               user=user,
                               pwd=pwd)
    except Exception as e:
            print("Error: ", e)
            raise SystemExit
    atexit.register(Disconnect, si)
    return si

def get_hosts(conn):
    print("Getting All hosts Objects")
    content = conn.RetrieveContent()
    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.HostSystem], True)
    obj = [host for host in container.view]
    return obj 

def set_traffic_shaping(host, v_switch_name, port_group_name):
    port_group_spec = vim.host.PortGroup.Specification()
    shaping_policy = vim.host.NetworkPolicy.TrafficShapingPolicy()
    shaping_policy.enabled = True
    shaping_policy.averageBandwidth = 300000000
    shaping_policy.peakBandwidth = 500000000
    shaping_policy.burstSize = 104857600
    port_group_spec.name = port_group_name
    port_group_spec.vswitchName = v_switch_name
    port_group_spec.policy = vim.host.NetworkPolicy(shapingPolicy=shaping_policy)
    try:
        host.configManager.networkSystem.UpdatePortGroup(port_group_name, port_group_spec)
        print 'Traffic Shaping for {} on host {} successfully set'.format(port_group_name, host.name)
    except Exception as e:
        print 'Setting Traffic Shaping for {} on host {} FAILED'.format(port_group_name, host)
        print("Error: ", e)

def main():
    si = vcenter_connection()
    # Get all hosts objects
    esxi_hosts = get_hosts(si)
    v_switch_name = "vSwitch0"
    port_group_name = "Management Network"

    for host in esxi_hosts:
        set_traffic_shaping(host, v_switch_name, port_group_name)
# Start program
if __name__ == "__main__":
    main()
