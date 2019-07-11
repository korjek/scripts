#!/usr/bin/python

from pyVim.connect import SmartConnectNoSSL, Disconnect
from pyVmomi import vim
import ConfigParser
import atexit
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient import discovery
from httplib2 import Http

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

def get_dc_list(si):
    """
    Get list of Datacenters in vCenter
    -> returns dict with {dc_object: dc_name} key-value pairs
    """
    content = si.RetrieveContent()
    dc_list = dict()
    for child in content.rootFolder.childEntity:
        if child.name == 'erfurt.elex.be':
            dc_list[child] = child.name
    return dc_list

def get_host_list(dc):
    """
    Get list of hosts in Datacenter
    -> returns dict of {host_object: host_name} key-value pairs
    """
    host_list = dict()
    for child in dc.hostFolder.childEntity:
        hosts = child.host
        for host in hosts:
            host_list[host] = host.summary.config.name
    return host_list

def get_vm_list(host):
    """
    Get list of Virtual Machines located on Host
    -> returns dict of {vm_object: vm_name key} key-value pairs"
    """
    vm_list = dict()
    for vm in host.vm:
        vm_list[vm] = vm.summary.config.name
    return vm_list

def get_host_params(host):
    """
    Get list of some Host parameters
    -> returns dict of {host_param_key: host_param_value} key-value pairs
    """
    host_params = dict()
    host_params["type"] = "vmware host"
    host_params["hostname"] = host.summary.config.name
    host_params["memory_size"] = round(host.summary.hardware.memorySize/1024.0/1024.0/1024.0, 2)
    host_params["num_cpu"] = host.summary.hardware.numCpuCores
    if host.runtime.connectionState == 'connected': 
        host_params["eth0_ip"] = host.config.network.vnic[0].spec.ip.ipAddress
        host_params["full_os_version"] = host.config.product.fullName
    else:
        host_params["eth0_ip"] = 'N/A'
        host_params["full_os_version"] = 'N/A'
    for custom_value in host.customValue:
        if custom_value.key == 501:
            host_params["blade"] = custom_value.value
        elif custom_value.key == 502:
            host_params["bay"] = custom_value.value
        elif custom_value.key == 503:
            host_params["date_of_installation"] = custom_value.value
        elif custom_value.key == 504:
            host_params["owner"] = custom_value.value
    return host_params

def get_all_vm_params(host):
    """ Get list of some parameters of all  Virtual Machines located on Host
    -> returns dict of dicts {vm_object: {vm_param_key: vm_param_value}} key-value pairs
    """
    vm_params = dict()
    for vm in host.vm:
        if not vm.config.template:
            hostname = vm.summary.config.name
            vm_params[hostname] = {}
            vm_params[hostname]["type"] = "vmware vm"
            vm_params[hostname]["hostname"] = vm.summary.config.name
            vm_params[hostname]["memory_size"] = vm.summary.config.memorySizeMB/1024
            vm_params[hostname]["num_cpu"] = vm.summary.config.numCpu
            vm_params[hostname]["eth0_ip"] = vm.guest.ipAddress
            vm_params[hostname]["full_os_version"] = vm.summary.config.guestFullName
            vm_params[hostname]["date_of_installation"] = None
            for custom_value in vm.customValue:
                if custom_value.key == 501:
                    vm_params[hostname]["owner"] = custom_value.value
        else:
            hostname = vm.summary.config.name
            vm_params[hostname] = {}
            vm_params[hostname]["type"] = "vmware vm template"
            vm_params[hostname]["hostname"] = vm.summary.config.name
            vm_params[hostname]["memory_size"] = 0
            vm_params[hostname]["num_cpu"] = 0
            vm_params[hostname]["eth0_ip"] = vm.guest.ipAddress
            vm_params[hostname]["full_os_version"] = vm.summary.config.guestFullName
            vm_params[hostname]["date_of_installation"] = None
            for custom_value in vm.customValue:
                if custom_value.key == 501:
                    vm_params[hostname]["owner"] = custom_value.value
    return vm_params

def get_current_sheet_id(service, spreadsheet_id, title):
    sheets_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = sheets_metadata.get('sheets', {})
    for sheet in sheets:
        sheet_title = sheet.get("properties", {}).get("title")
        sheet_id = sheet.get("properties", {}).get("sheetId")
        if (sheet_title == title):
            return sheet_id

def next_available_row(worksheet):
    str_list = filter(None, worksheet.col_values(1))
    return str(len(str_list)+1)

def make_row_frozen(service, spreadsheet_id, sheet_id):
    reqs = {'requests': [
        {'updateSheetProperties': {
            'properties': {'sheetId': sheet_id, 'gridProperties': {'frozenRowCount': 1}},
            'fields': 'gridProperties.frozenRowCount'
        }}
    ]}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=reqs).execute()

def insert_row(service, spreadsheet_id, current_sheet_title, range, values, value_input_option):
    range = current_sheet_title +'!' + range
    service.spreadsheets().values().update(spreadsheetId=spreadsheet_id, range=range, body={'values': values}, valueInputOption=value_input_option).execute()

def adjust_column_size(service, spreadsheet_id, sheet_id, start_column, end_column):
    reqs = {'requests': [
        {'autoResizeDimensions': {
            'dimensions': {
                'sheetId': sheet_id,
                'dimension': 'COLUMNS',
                'startIndex': start_column,
                'endIndex': end_column
            }
        }}
    ]}
    
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=reqs).execute()

def add_worksheet(service, spreadsheet_id, title, row_count, column_count):
    reqs = {'requests': [
        {'addSheet': {
            'properties': {
                'title': title,
                'gridProperties': {
                    'rowCount': row_count,
                    'columnCount': column_count
                }
            }
       }}
    ]}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=reqs).execute()

def delete_worksheet(service, spreadsheet_id, sheet_id):
    reqs ={'requests': [
        {'deleteSheet': {
        'sheetId': sheet_id
        }}
    ]}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=reqs).execute()

def clear_worksheet(service, spreadsheet_id, sheet_id):
    reqs = {'requests': [
        {'updateCells': {
            'range': {
                'sheetId': sheet_id
            },
            'fields': 'userEnteredValue'
        }},
        {'updateCells': {
            'range': {
                'sheetId': sheet_id
            },
            'fields': 'userEnteredFormat'
        }},
        {'deleteConditionalFormatRule': {
            'sheetId': sheet_id,
            'index': 0
        }}
    ]}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=reqs).execute()

def make_row_bold(service, spreadsheet_id, sheet_id, start_row, end_row):
    reqs = {'requests': [
        {'repeatCell': {
            'range': {
                'sheetId': sheet_id,
                'startRowIndex': start_row,
                'endRowIndex': end_row,
            },
            'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
            'fields': 'userEnteredFormat.textFormat.bold',
        }},
    ]}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=reqs).execute()    

def make_cell_percentage(service, spreadsheet_id, sheet_id, start_row, end_row, start_column, end_column):
    reqs = {'requests': [
        {'repeatCell': {
            'range': {
                'sheetId': sheet_id,
                'startRowIndex': start_row,
                'endRowIndex': end_row,
                'startColumnIndex': start_column,
                'endColumnIndex': end_column
            },
            'cell': {
                'userEnteredFormat': {
                    'numberFormat': {
                        'type': 'PERCENT',
                        'pattern': '0.00%'
                    }
                }
            },
            'fields': 'userEnteredFormat.numberFormat'
        }}
    ]}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=reqs).execute()

def make_conditional_formatting(service, spreadsheet_id, sheet_id, start_row, end_row):
    reqs = {'requests': [
        {'addConditionalFormatRule': {
            'rule': {
                'ranges': [{
                    'sheetId': sheet_id,
                    'startColumnIndex': 0,
                    'endColumnIndex': 2,
                    'startRowIndex': start_row,
                    'endRowIndex': end_row
                }],
                'booleanRule': {
                    'condition': {
                        'type': 'NUMBER_LESS',
                        'values': [{
                            "userEnteredValue": '0.8'
                        }]
                    },
                    'format': {
                        'backgroundColor': { 'red': 0, 'green': 0.62, 'blue': 0.26 }
                    },
                }
            },
            'index': 0
        }},
        {'addConditionalFormatRule': {
            'rule': {
                'ranges': [{
                    'sheetId': sheet_id,
                    'startColumnIndex': 0,
                    'endColumnIndex': 2,
                    'startRowIndex': start_row,
                    'endRowIndex': end_row
                }], 
                'booleanRule': {
                    'condition': {
                        'type': 'NUMBER_BETWEEN',
                        'values': [
                            {"userEnteredValue": '0.8'},
                            {"userEnteredValue": '0.9'},
                        ]  
                    },  
                    'format': {
                        'backgroundColor': { 'red':1, 'green': 0.47, 'blue': 0 }
                    },  
                }   
            },
            'index': 0
        }},
        {'addConditionalFormatRule': {
            'rule': {
                'ranges': [{
                    'sheetId': sheet_id,
                    'startColumnIndex': 0,
                    'endColumnIndex': 2,
                    'startRowIndex': start_row,
                    'endRowIndex': end_row
                }],
                'booleanRule': {
                    'condition': {
                        'type': 'NUMBER_GREATER',
                        'values': [{
                            "userEnteredValue": '0.9'
                        }]
                    },
                    'format': {
                        'backgroundColor': { 'red': 0.76, 'green': 0.16, 'blue': 0.2 }
                    },
                }
            },
            'index': 0
        }}
    ]}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=reqs).execute()


def main():
    SCOPE = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', SCOPE)
    service = discovery.build('sheets', 'v4', http=creds.authorize(Http()))
    SPREADSHEET_ID = '1yCP93cXDjm3m40iiTsS5vNi1lm08LHEO3ptuRBJbXVo'

    si = None
    si = vcenter_connection()
    dc_list = get_dc_list(si)
    columns = 6
    rows = 800

    for k, v in dc_list.iteritems():
        current_sheet_id = None
        current_sheet_name = None
        index = 1
        host_index = index
        stat_index = None
        summary_values = list()
        try:
            add_worksheet(service, SPREADSHEET_ID, v, rows , columns)
        except:
            current_sheet_id = get_current_sheet_id(service, SPREADSHEET_ID, v)
            delete_worksheet(service, SPREADSHEET_ID, current_sheet_id) 
            add_worksheet(service, SPREADSHEET_ID, v, rows, columns)
        head_row_values = [["MEM", "CPU", "TYPE", "HOSTNAME", "ETH0", "OS Release"]]
        current_sheet_name = v
        current_sheet_id = get_current_sheet_id(service, SPREADSHEET_ID, current_sheet_name)
        insert_row(service, SPREADSHEET_ID, current_sheet_name, 'A1:F1', head_row_values, 'RAW')
        make_row_frozen(service, SPREADSHEET_ID, current_sheet_id)
        make_row_bold(service, SPREADSHEET_ID, current_sheet_id, 0, 1)
        host_list = get_host_list(k)
        for k, v in host_list.iteritems():
            vm_count = 0
            host_index = index + 2
            vm_list = get_vm_list(k)
            vm_count = len(vm_list)
            stat_index = host_index + vm_count + 1
            index = stat_index
            host_values = list()
            vm_values = list()
            order_params = ["memory_size", "num_cpu", "type", "hostname", "eth0_ip", "full_os_version"]
            host_params = get_host_params(k)
            host_value = [host_params.get(x) for x in order_params]
            host_values = [[' '] * columns, host_value]
            host_range = 'A' + str(host_index-1) + ':F' + str(host_index)
            insert_row(service, SPREADSHEET_ID, current_sheet_name, host_range, host_values, 'RAW')
            vm_range = 'A' + str(host_index + 1) + ':F' + str(stat_index)
            vm_params = get_all_vm_params(k)
            for k, v in vm_params.iteritems():
                vm_value = [vm_params.get(k, {}).get(x) for x in order_params]
                vm_values.append(vm_value)
            insert_row(service, SPREADSHEET_ID, current_sheet_name, vm_range, vm_values, 'RAW')
            stat_values = [['=ArrayFormula(DIVIDE(SUM(A{}:A{}),A{}))'.format(host_index+1, host_index+vm_count, host_index), '=ArrayFormula(DIVIDE(SUM(B{}:B{}),B{}))'.format(host_index+1, host_index+vm_count, host_index), '="Free MEM = " & A{}-Sum(A{}:A{}) & " Free CPU = " & B{}-Sum(B{}:B{})'.format(host_index, host_index+1, host_index+vm_count,host_index, host_index+1, host_index+vm_count)]]
            stat_range = 'A' + str(stat_index) + ':C' + str(stat_index)
            insert_row(service, SPREADSHEET_ID, current_sheet_name, stat_range, stat_values, 'USER_ENTERED')
            make_row_bold(service, SPREADSHEET_ID, current_sheet_id, host_index-1, host_index)
            make_row_bold(service, SPREADSHEET_ID, current_sheet_id, stat_index-1, stat_index)
            make_conditional_formatting(service, SPREADSHEET_ID, current_sheet_id, stat_index-1, stat_index)
            make_cell_percentage(service, SPREADSHEET_ID, current_sheet_id, stat_index-1, stat_index, 0, 2)

        empty_line = ['', '', '']
        summary_host = ['', 'VMWare Host', '=countif(C:C,"vmware host")']
        summary_vm = ['', 'VMWare VM', '=countif(C:C,"vmware vm")']
        summary_debian_lenny = ['Debian', 'lenny', '=countif(F:F,"Debian GNU/Linux 5*")']
        summary_debian_squeeze = ['', 'squeeze', '=countif(F:F,"Debian GNU/Linux 6*")']
        summary_debian_wheezy = ['', 'wheezy', '=countif(F:F,"Debian GNU/Linux 7*")']
        summary_redhat_4 = ['RedHat', '4.x', '=countif(F:F,"Red Hat Enterprise Linux 4*")']
        summary_redhat_5 = ['', '5.x', '=countif(F:F,"Red Hat Enterprise Linux 5*")']
        summary_redhat_6 = ['', '6.x', '=countif(F:F,"Red Hat Enterprise Linux 6*")']
        summary_redhat_7 = ['', '7.x', '=countif(F:F,"Red Hat Enterprise Linux 7*")']
        summary_windows_xp = ['Windows', 'XP', '=countif(F:F,"Microsoft Windows XP*")']
        summary_windows_7 = ['', '7','=countif(F:F,"Microsoft Windows 7*")']
        summary_windows_2003 = ['', '2003', '=countif(F:F,"Microsoft Windows Server 2003*")']
        summary_windows_2008 = ['', '2008', '=countif(F:F,"Microsoft Windows Server 2008*")']
        summary_windows_2012 = ['', '2012', '=countif(F:F,"Microsoft Windows Server 2012*")']
        summary_total_vmware_host_mem = ['', 'Total VMWare MEM', '=SUM(filter(A:A,C:C="vmware host"))']
        summary_used_vmware_host_mem = ['', 'Used VMWare MEM', '=SUM(filter(A:A,C:C="vmware vm"))']
        summary_total_vmware_host_cpu = ['', 'Total VMWare CPU', '=SUM(filter(B:B,C:C="vmware host"))']
        summary_used_vmware_host_cpu = ['', 'Used VMWare CPU', '=SUM(filter(B:B,C:C="vmware vm"))']
        summary_test_used_mem = ['', 'VMWare MEM used on TEST', '=SUM(QUERY(A:D,"select A where C matches \'vmware vm\' and D contains \'test\'"))']
        summary_uat_used_mem = ['', 'VMWare MEM used on UAT', '=SUM(QUERY(A:D,"select A where C matches \'vmware vm\' and D contains \'uat\'"))']
        summary_prod_used_mem = ['', 'VMWare MEM used on PROD', '=SUM(QUERY(A:D,"select A where C matches \'vmware vm\' and not D contains \'test\' and not D contains \'uat\'"))']
        summary_test_used_cpu = ['', 'VMWare CPU used on TEST', '=SUM(QUERY(A:D,"select B where C matches \'vmware vm\' and D contains \'test\'"))']
        summary_uat_used_cpu = ['', 'VMWare CPU used on UAT', '=SUM(QUERY(A:D,"select B where C matches \'vmware vm\' and D contains \'uat\'"))']
        summary_prod_used_cpu = ['', 'VMWare CPU used on PROD', '=SUM(QUERY(A:D,"select B where C matches \'vmware vm\' and not D contains \'test\' and not D contains \'uat\'"))']
        summary_all = [summary_host, summary_vm, empty_line, summary_debian_lenny, summary_debian_squeeze, summary_debian_wheezy, empty_line, summary_redhat_4, summary_redhat_5, summary_redhat_6, summary_redhat_7, empty_line, summary_windows_xp, summary_windows_7, summary_windows_2003, summary_windows_2008, summary_windows_2012, empty_line, summary_total_vmware_host_mem, summary_used_vmware_host_mem, empty_line, summary_total_vmware_host_cpu, summary_used_vmware_host_cpu, empty_line, summary_test_used_mem, summary_uat_used_mem, summary_prod_used_mem, empty_line, summary_test_used_cpu, summary_uat_used_cpu, summary_prod_used_cpu]
        for summary_item in summary_all:
            summary_values.append(summary_item)
        summary_range = 'C' + str(index + 4) + ':E' + str(index + 3 + len(summary_all))
        insert_row(service, SPREADSHEET_ID, current_sheet_name, summary_range, summary_values, 'USER_ENTERED')

        adjust_column_size(service, SPREADSHEET_ID, current_sheet_id, 0, columns)

# Start program
if __name__ == "__main__":
    main()
