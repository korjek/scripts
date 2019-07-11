#!/usr/bin/python

from __future__ import print_function

import pyVmomi

from pyVmomi import vim
from pyVmomi import vmodl

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vmodl

from common import config_parser
import argparse
import random
import atexit
import getpass
import time
import ssl
import requests
import os


#Surpress InsecureRequestWarning
requests.packages.urllib3.disable_warnings()


def get_hosts(conn):
    print("Getting All hosts Objects")
    content = conn.RetrieveContent()
    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.HostSystem], True)
    obj = [host for host in container.view]
    return obj


def vcenter_connection(host=None,user=None,pwd=None,port=443):
    config = "/etc/esxi.config"
    if os.path.exists(config):
        vcenter_conf = config_parser(config, 'VCENTER')
        host = vcenter_conf['host']
        user = vcenter_conf['user']
        pwd = vcenter_conf['pwd']
        port = vcenter_conf['port']
    try:
        sslContext = ssl.create_default_context()
        sslContext.check_hostname = False
        sslContext.verify_mode = ssl.CERT_NONE
    except:
        sslContext = None

    try:
        si = SmartConnect(host=host,user=user,
                          pwd=pwd,port=port,
                          sslContext=sslContext)
    except Exception as e:
        print("Error: ", e)
        raise SystemExit
    atexit.register(Disconnect, si)
    content = si.RetrieveContent()
    return si, content


def get_obj(content, vimtype, name):
    """
     Get the vsphere object associated with a given text name
    """
    obj = None
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for c in container.view:
        if c.name == name:
            obj = c
            break
    return obj


def get_all_objs(content, vimtype):
    """
    Get all the vsphere objects associated with a given type
    """
    obj = {}
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for c in container.view:
        obj.update({c: c.name})
    return obj


def get_all_obj_by_name(content, vimtype, name):
    """
     Get the vsphere object associated with a given text name
    """
    obj = []
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for c in container.view:
        if c.name == name:
            obj.append(c)
    return obj


def get_vm_mac(vm_name, content):
    vm = get_obj(content, [vim.VirtualMachine], vm_name)
    for device in vm.config.hardware.device:
        if isinstance(device, vim.vm.device.VirtualEthernetCard):
            print("MAC Address: ", device.macAddress)
            #print(device.connectable)
    return device.macAddress


def get_vm_uuid(vm_name, content):
    vm = get_obj(content, [vim.VirtualMachine], vm_name)
    try:
        vm_uuid = vm.config.instanceUuid
        return vm_uuid
    except Exception as e:
        print('Error:', e)


def host_swap_usage(hostname, content):
    host = content.searchIndex.FindByDnsName(dnsName=hostname, vmSearch=False)
    for vm in host.vm:
        print(vm.summary.quickStats.swappedMemory, "\tswap on", vm.name)


def print_dc_mem(dc):
    print("\nDATACENTER: ", dc.name, "\n")
    for cluster in dc.hostFolder.childEntity:
        if cluster.name == 'PROD':
            for host in cluster.host:
                host_memory = int(host.summary.hardware.memorySize / 1024 / 1024)
                total_vm_mem = 0 
                for vm in host.vm:
                    total_vm_mem = total_vm_mem + vm.summary.config.memorySizeMB
                print(host.name, " memory:", host_memory)
                print("Free memory:", host_memory - total_vm_mem)


def get_esxi_most_mem(dc):
    max_mem = 0
    esxi_host = None
    print("\nDATACENTER: ", dc.name, "\n")
    for cluster in dc.hostFolder.childEntity:
        if cluster.name == 'PROD':
            for host in cluster.host:
                host_memory = int(host.summary.hardware.memorySize / 1024 / 1024)
                total_vm_mem = 0
                for vm in host.vm:
                    total_vm_mem = total_vm_mem + vm.summary.config.memorySizeMB
                free_mem = host_memory - total_vm_mem
                if max(free_mem, max_mem) == free_mem:
                    esxi_host = host
    print(esxi_host.name)
    return esxi_host, esxi_host.name


def wait_for_task(task, action_name='job', hide_result=False):
    print('Waiting for {} to complete.'.format(action_name))
    while task.info.state == vim.TaskInfo.State.running:
       print('progress: {}% ...'.format(task.info.progress))
       time.sleep(5)

    if task.info.state == vim.TaskInfo.State.success:
       if task.info.result is not None and not hide_result:
          out = '{} completed successfully, result: {}'.format(action_name, task.info.result)
       else:
          out = '{} completed successfully.'.format(action_name)
    else:
       out = '{} did not complete successfully: {}'.format(action_name, task.info.error)
       print(out)
       raise task.info.error # should be a Fault... check

    # may not always be applicable, but can't hurt.
    return task.info.result


def get_host_with_highest_free_mem(si, datacenter, cluster, exclude_host):
    """
    Function search for ESXi with free RAM  with highest free RAM for specific datacenter and cluster
    except specified host (exclude_host parameter) and returns this host with free RAM data
    """
    highestFreeMem = 0
    hostWithHighestFreeMem = None
    content = si.RetrieveContent()
    for child in content.rootFolder.childEntity:
        if (child.name == datacenter):
            dc = child
            cls = dc.hostFolder.childEntity
            for cl in cls:
                if cl.name == cluster:
                    hss = cl.host
                    for hs in hss:
                        if not (hs.summary.config.name == exclude_host):
                            summary = hs.summary
                            hardware = hs.hardware
                            stats = summary.quickStats
                            memoryCapacity = hardware.memorySize/MBFACTOR
                            memoryUsage = stats.overallMemoryUsage
                            freeMemory = memoryCapacity - memoryUsage
                            if freeMemory > highestFreeMem:
                                highestFreeMem = freeMemory
                                hostWithHighestFreeMem = hs
    return hostWithHighestFreeMem, highestFreeMem

def get_vm_with_mem_size(si, datacenter, cluster, host):
    """
    Function returns VM objest with it's name and RAM configured
    """
    vmWithMemSize = {}
    content = si.RetrieveContent()
    for child in content.rootFolder.childEntity:
        if (child.name == datacenter):
            dc = child
            cls = dc.hostFolder.childEntity
            for cl in cls:
                if cl.name == cluster:
                    hss = cl.host
                    for hs in hss:
                        if (hs.summary.config.name == host):
                            vms = hs.vm
                            for vm in vms:
                                vmWithMemSize.setdefault(vm, [])
                                vmWithMemSize[vm].append(vm.summary.config.name)
                                vmWithMemSize[vm].append(vm.summary.config.memorySizeMB)
    return vmWithMemSize

def get_datacenter(esxi_host):
    """
    Function returns datacenter name from host name
    """
    datacenter = "".join(str(x) for x in esxi_host.split(".", 1)[1:])
    return datacenter

def get_hosts_with_esxi_version(si, datacenter):
    hosts_with_esxi_version = {}
    content = si.RetrieveContent()
    for child in content.rootFolder.childEntity:
        if (child.name == datacenter):
            dc = child
            cls = dc.hostFolder.childEntity
            for cl in cls:
                hss = cl.host
                for hs in hss:
                    hosts_with_esxi_version[hs.summary.config.name] = hs.summary.config.product.version
    return hosts_with_esxi_version



def get_random_host(si, content, datacenter):
    search_index = si.content.searchIndex
    dc = search_index.FindByInventoryPath('/{}'.format(datacenter))
    for cluster in dc.hostFolder.childEntity:
        if cluster.name == 'PROD':
            host = cluster.host[random.randrange(len(cluster.host))]
    print('Randomly selected {}'.format(host.name))
    return host
