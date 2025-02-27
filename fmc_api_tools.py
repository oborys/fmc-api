# Import Required Modules
import os,\
        re,\
        sys,\
        csv,\
        json,\
        socket,\
        random,\
        netaddr,\
        netmiko,\
        getpass,\
        requests,\
        warnings,\
        traceback
from datetime import datetime
from ipaddress import IPv4Network

# Import custom modules from file
from fmc_api_module import \
        define_password,\
        access_token,\
        get_device_details,\
        get_net_object_uuid, \
        select,\
        get_items,\
        parse_rule,\
        put_bulk_acp_rules

# Disable SSL warning
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

#
#
#
# Define Blank URL Get Script as Function
def blank_get(server,headers,username,password):
    print ('''
***********************************************************************************************
*                             Basic URL GET Script                                            *
*_____________________________________________________________________________________________*
*                                                                                             *
* USER INPUT NEEDED:                                                                          *
*                                                                                             *
*  1. URI Path (/api/fmc_config/v1/domain/{domain_UUID}/object/networkgroups/{object_UUID})   *
*                                                                                             *
*  2. Expand output to show details of each object *(Not Supported with {object_UUID} GET)    *
*                                                                                             *
*  3. Limit output to a specific number of objects *(Not Supported with {object_UUID} GET)    *
*                                                                                             *
*  4. Save output to file                                                                     *
*                                                                                             *
*                                                                                             *
***********************************************************************************************
''')

    print('Generating Access Token')
    # Generate Access Token and pull domains from auth headers
    results=access_token(server,headers,username,password)
    headers['X-auth-access-token']=results[0]

    # Request API URI Path
    api_path = input('Please Enter URI: ').lower().strip()

    # Clean URI
    if (api_path[-1] == '/'):
        api_path = api_path[:-1]

    # Check for GETBYID Operation in URI
    getbyid = re.match('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', api_path[-36:])

    # Set URL
    url = f'{server}{api_path}'

    # Ask to Expand and/or assign output Limit
    if getbyid == None:
        expand = input('Would You Like To Expand Output Entries? [y/N]: ').lower()
        limit = input('Would You Like To Limit Output Entries? [Number or "No"]: ').lower()

        if limit not in (['no','n','']) and expand in (['yes','ye','y']):
            url = f'{server}{api_path}?expanded=true&limit={limit}'
        elif limit not in (['no','n','']) and expand in (['no','n','']):
            url = f'{server}{api_path}?limit={limit}'
        elif limit in (['no','n','']) and expand in (['yes','ye','y']):
            url = f'{server}{api_path}?expanded=true'
    if url[-1] == '/':
        url = url[:-1]

    # Perform API GET call
    print(f'Performing API GET to: {url}')
    try:
        # REST call with SSL verification turned off:
        r = requests.get(url, headers=headers, verify=False)
        status_code = r.status_code
        resp = r.json()
        if (status_code == 200):
            print('GET successful...')
            # Ask if output should be saved to File
            save = input('Would You Like To Save The Output To File? [y/N]: ').lower()
            if save in (['yes','ye','y']):
                # Random Generated JSON Output File
                filename = ''.join(i for i in [chr(random.randint(97,122)) for i in range(6)])
                filename += '.json'
                print(f'*\n*\nRANDOM LOG FILE CREATED... {filename}\n')
                with open(filename, 'a') as OutFile:
                    OutFile.write(json.dumps(resp,indent=4))
            elif save in (['no','n','']):
                print(json.dumps(resp,indent=4))
        else:
            r.raise_for_status()
            print(f'Error occurred in GET --> {resp}')
    except requests.exceptions.HTTPError as err:
        print(f'Error in connection --> {err}')
        print(json.dumps(resp,indent=4))
    # End
    finally:
        try:
            if r: r.close()
        except:
            None


#
#
#
# Define Network Object POST Script as Funtion
def post_network_object(server,headers,username,password):
    print ('''
***********************************************************************************************
*                          Create Network Objects in bulk                                     *
*_____________________________________________________________________________________________*
*                                                                                             *
* USER INPUT NEEDED:                                                                          *
*                                                                                             *
*  1. Select Object type                                                                      *
*                                                                                             *
*  2. CSV Data Input file                                                                     *
*       # CSV FORMAT:                                                                         *
*           No Header Row & comma delimited                                                   *
*           Can contain Host, Range, Network or FQDN objects, not a combination               *
*           Column0 = ObjectName                                                              *
*           Column1 = Address                                                                 *
*                                                                                             *
***********************************************************************************************
''')

    print('Generating Access Token')
    # Generate Access Token and pull domains from auth headers
    results=access_token(server,headers,username,password)
    headers['X-auth-access-token']=results[0]
    domains = results[1]

    if len(domains) > 1:
        API_UUID = select('Domain',domains)['uuid']
    else:
        API_UUID = domains[0]['uuid']

    objTypes = [
        {
            'name':'Host',
            'url':f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/hosts?bulk=true'
        },
        {
            'name':'Range',
            'url':f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/ranges?bulk=true'
        },
        {
            'name':'Network',
            'url':f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/networks?bulk=true'
        },
        {
            'name':'FQDN',
            'url':f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/fqdns?bulk=true'
        }
    ]
    # Select type of Object to post
    objType = select('Object Type',objTypes)

    Test = False

    while not Test:
        # Request Input File
        read_csv = input('Please Enter Input File /full/file/path.csv: ')
        if os.path.isfile(read_csv):
            # Read csv file
            open_read_csv = open(read_csv, 'r')
            my_csv_reader = csv.reader(open_read_csv, delimiter=',')
            Test = True
        else:
            print('MUST PROVIDE INPUT FILE...')

    post_data = []
    # Create For Loop To Process Each Item In CSV
    for row in my_csv_reader:
        objName = row[0]
        address = row[1]
        post_data.append({
            'name': objName,
            'type': objType['name'],
            'description': '',
            'value': address
        })

    try:
        # REST call with SSL verification turned off:
        url = objType['url']
        r = requests.post(url, data=json.dumps(post_data), headers=headers, verify=False)
        status_code = r.status_code
        resp = r.text
        print(f'Status code is: {status_code}')
        if status_code == 201 or status_code == 202:
            print('Network Objects successfully created...')
        else :
            print(f'Error occurred in POST --> {json.dumps(r.json(),indent=4)}')
            r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print (f'Error in connection --> {traceback.format_exc()}')
    finally:
        try:
            if r: r.close()
        except:
            None

#
#
#
# Define Network Object-Group POST Script as Funtion
def post_network_object_group(server,headers,username,password):
    print ('''
***********************************************************************************************
*                     Create Network Objects and Object Groups in bulk                        *
*_____________________________________________________________________________________________*
*                                                                                             *
* USER INPUT NEEDED:                                                                          *
*                                                                                             *
*  1. TXT Data Input file                                                                     *
*       # Output from ASA "show run object network" and "show run object-group network"       *
*       # Ensure no object names overlap with existing objects                                *
*       # Ensure nested groups are above groups nesting them                                  *
*                                                                                             *
***********************************************************************************************
''')

    print('Generating Access Token')
    # Generate Access Token and pull domains from auth headers
    results=access_token(server,headers,username,password)
    headers['X-auth-access-token']=results[0]
    domains = results[1]

    if len(domains) > 1:
        API_UUID = select('Domain',domains)['uuid']
    else:
        API_UUID = domains[0]['uuid']

    Test = False
    while not Test:
        # Request Input File
        read_file = input('Please Enter Input File /full/file/path.txt: ').strip()
        if os.path.isfile(read_file):
            # Read csv file
            open_read_file = open(read_file, 'r').read()
            Test = True
        else:
            print('MUST PROVIDE INPUT FILE...')

    tempData = {
        'objects':[],
        'groups':[]
    }

    SPLIT = re.split(r'\nobject',open_read_file)
    for item in SPLIT:
        obj = item.splitlines()
        name = obj[0].split()[-1]
        if obj[0].startswith('-group'):
            obj.pop(0)
            tempData['groups'].append({'name':name,'entries':obj})
        else:
            obj.pop(0)
            tempData['objects'].append({'name':name,'entry':obj[0].strip()})

    Data = {
        'objects': {
            'Host':[],
            'Network':[],
            'Range':[],
            'FQDN':[]
        },
        'groups':{}
    }

    for obj in tempData['objects']:
        objName = obj['name']
        if obj['entry'].startswith('host'):
            objType = 'Host'
            address = obj['entry'].split()[-1]
            Data['objects']['Host'].append({
                'name': objName,
                'type': objType,
                'description': '',
                'value': address
            })
        elif obj['entry'].startswith('subnet'):
            objType = 'Network'
            address = f'{obj["entry"].split()[-2]}/{obj["entry"].split()[-1]}'
            Data['objects']['Network'].append({
                'name': objName,
                'type': objType,
                'description': '',
                'value': address
            })
        elif obj['entry'].startswith('range'):
            objType = 'Range'
            address = f'{obj["entry"].split()[-2]}-{obj["entry"].split()[-1]}'
            Data['objects']['Range'].append({
                'name': objName,
                'type': objType,
                'description': '',
                'value': address
            })
        if obj['entry'].startswith('fqdn'):
            objType = 'FQDN'
            address = obj['entry'].split()[-1]
            Data['objects']['FQDN'].append({
                'name': objName,
                'type': objType,
                'description': '',
                'value': address
            })


    # Post Host objects, and store JSON response with object uuids
    try:
        # REST call with SSL verification turned off:
        post_data = Data['objects']['Host']
        url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/hosts?bulk=true'
        r = requests.post(url, data=json.dumps(post_data), headers=headers, verify=False)
        status_code = r.status_code
        resp = r.text
        print(f'Status code is: {status_code}')
        if status_code == 201 or status_code == 202:
            print('Network Objects successfully created...')
            Data['objects']['Host'] = r.json()['items']
        else :
            print(f'Error occurred in POST --> {json.dumps(r.json(),indent=4)}')
            r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print (f'Error in connection --> {traceback.format_exc()}')
    finally:
        try:
            if r: r.close()
        except:
            None

    # Post Network objects, and store JSON response with object uuids
    try:
        # REST call with SSL verification turned off:
        post_data = Data['objects']['Network']
        url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/networks?bulk=true'
        r = requests.post(url, data=json.dumps(post_data), headers=headers, verify=False)
        status_code = r.status_code
        resp = r.text
        print(f'Status code is: {status_code}')
        if status_code == 201 or status_code == 202:
            print('Network Objects successfully created...')
            Data['objects']['Network'] = r.json()['items']
        else :
            print(f'Error occurred in POST --> {json.dumps(r.json(),indent=4)}')
            r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print (f'Error in connection --> {traceback.format_exc()}')
    finally:
        try:
            if r: r.close()
        except:
            None

    # Post Ranges objects, and store JSON response with object uuids
    try:
        # REST call with SSL verification turned off:
        post_data = Data['objects']['Range']
        url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/ranges?bulk=true'
        r = requests.post(url, data=json.dumps(post_data), headers=headers, verify=False)
        status_code = r.status_code
        resp = r.text
        print(f'Status code is: {status_code}')
        if status_code == 201 or status_code == 202:
            print('Network Objects successfully created...')
            Data['objects']['Range'] = r.json()['items']
        else :
            print(f'Error occurred in POST --> {json.dumps(r.json(),indent=4)}')
            r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print (f'Error in connection --> {traceback.format_exc()}')
    finally:
        try:
            if r: r.close()
        except:
            None

    # Post FQDN objects, and store JSON response with object uuids
    try:
        # REST call with SSL verification turned off:
        post_data = Data['objects']['FQDN']
        url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/fqdns?bulk=true'
        r = requests.post(url, data=json.dumps(post_data), headers=headers, verify=False)
        status_code = r.status_code
        resp = r.text
        print(f'Status code is: {status_code}')
        if status_code == 201 or status_code == 202:
            print('Network Objects successfully created...')
            Data['objects']['FQDN'] = r.json()['items']
        else :
            print(f'Error occurred in POST --> {json.dumps(r.json(),indent=4)}')
            r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print (f'Error in connection --> {traceback.format_exc()}')
    finally:
        try:
            if r: r.close()
        except:
            None

    for obj in tempData['groups']:
        objName = obj['name']
        Obj = {
            'name': objName,
            'type': 'NetworkGroup',
            'objects': [],
            'literals': []
        }
        for item in obj['entries']:
            if 'network-object host ' in item:
                address = item.split()[-1]
                Obj['literals'].append({
                    'type': 'Host',
                    'value': address
                })
            elif 'network-object object ' in item:
                nestObjName = item.split()[-1]
                for k,v in Data['objects'].items():
                    for i in v:
                        if i['name'] == nestObjName:
                            Obj['objects'].append({
                                'type': i['type'],
                                'id': i['id']
                            })
            elif 'network-object ' in item:
                address = f'{item.split()[-2]}/{item.split()[-1]}'
                Obj['literals'].append({
                    'type': 'Network',
                    'value': address
                })
            elif 'group-object ' in item:
                nestObjName = item.split()[-1]
                i = Data['groups'][nestObjName]
                Obj['objects'].append({
                    'type': i['type'],
                    'id': i['id']
                })

        # Post object group, and store JSON response with object uuids
        try:
            # REST call with SSL verification turned off:
            post_data = Obj
            url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/networkgroups'
            r = requests.post(url, data=json.dumps(post_data), headers=headers, verify=False)
            status_code = r.status_code
            resp = r.text
            print(f'Status code is: {status_code}')
            if status_code == 201 or status_code == 202:
                print('Network Object Group successfully created...')
                Data['groups'].update({objName:r.json()})
            else :
                print(f'Error occurred in POST --> {json.dumps(r.json(),indent=4)}')
                r.raise_for_status()
        except requests.exceptions.HTTPError as err:
            print (f'Error in connection --> {traceback.format_exc()}')
        finally:
            try:
                if r: r.close()
            except:
                None


#
#
#
# Define IPS/File Policy Put Script as Funtion
def put_intrusion_file(server,headers,username,password):
    print ('''
***********************************************************************************************
*                     Update IPS and/or File Policy for Access Rules                          *
*_____________________________________________________________________________________________*
*                                                                                             *
* USER INPUT NEEDED:                                                                          *
*                                                                                             *
*  1. Select Access Policy                                                                    *
*                                                                                             *
*  2. Apply IPS and File Policy to ALL rules [y/N]                                            *
*       Note: Selecting NO will apply changes only to rules                                   *
*               which currently have IPS/File policy applied                                  *
*                                                                                             *
*  3. Select Intrusion Policy and Variable Set to apply to ALL rules                          *
*       Note: Selecting 'None' will NOT remove currently applied policy                       *
*                                                                                             *
*  4. Select File Policy to apply to ALL rules                                                *
*       Note: Selecting 'None' will NOT remove currently applied policy                       *
*                                                                                             *
***********************************************************************************************
''')

    print('Generating Access Token')
    # Generate Access Token and pull domains from auth headers
    results=access_token(server,headers,username,password)
    headers['X-auth-access-token']=results[0]
    domains = results[1]

    if len(domains) > 1:
        API_UUID = select('Domain',domains)['uuid']
    else:
        API_UUID = domains[0]['uuid']

    all_rules = False
    Test = False
    while not Test:
        choice = input('Would You Like To Apply IPS and File Policy to ALL rules ? [y/N]: ').lower()
        if choice in (['yes','ye','y']):
            all_rules = True
            Test = True
        elif choice in (['no','n','']):
            Test = True
        else:
            print('Invalid Selection...\n')


    # Get all Access Control Policies
    print('*\n*\nCOLLECTING Access Policies...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/policy/accesspolicies?expanded=true&offset=0&limit=1000'
    acp_list = get_items(url,headers)

    acp = select('Access Control Policy',acp_list)
    #print(json.dumps(acp,indent=4))

    # Get all Access Control Policy rules
    print('*\n*\nCOLLECTING Access Policy rules...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/policy/accesspolicies/{acp["id"]}/accessrules?offset=0&limit=1000&expanded=true'
    acp_rules = get_items(url,headers)

    # Get all Intrusion Policies
    print('*\n*\nCOLLECTING Intusion Policies...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/policy/intrusionpolicies?offset=0&limit=1000'
    ips_list = get_items(url,headers)
    # Add None option
    ips_list.append({'None':'None'})
    ips = select('Intusion Policy',ips_list)
    #print(json.dumps(ips,indent=4))

    if ips:
        # Get all Variable Sets
        print('*\n*\nCOLLECTING Variable Sets...')
        url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/variablesets?offset=0&limit=1000'
        vset_list = get_items(url,headers)
        vset = select('Variable Set',vset_list)
    else:
        vset = None

    # Get all File Policies
    print('*\n*\nCOLLECTING File Policies...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/policy/filepolicies?offset=0&limit=1000'
    file_list = get_items(url,headers)
    # Add None option
    file_list.append({'None':'None'})
    filepolicy = select('File Policy',file_list)

    # Operate only on ALLOW rules
    acp_rules = [i for i in acp_rules if i['action'] == 'ALLOW']

    # Operate only on rules that have IPS/File policy
    if not all_rules:
        acp_rules = [i for i in acp_rules if ('ipsPolicy' in i) or ('filePolicy' in i)]

    # Exit if no IPS or File Policy Selected
    if (not ips) and (not filepolicy):
        print(f'*\n*\nNo IPS or File policy selected, Exiting...\n')
        return

    # For Loop to update all rules
    for item in acp_rules:
        if (ips) and ((all_rules) or ('ipsPolicy' in item)):
            # Create IPS Policy
            item ['ipsPolicy'] = {}
            # Assign Values
            item ['ipsPolicy']['id'] = ips['id']
            item ['ipsPolicy']['name'] = ips['name']
            item ['ipsPolicy']['type'] = 'IntrusionPolicy'
            # Create VariableSet
            item ['variableSet'] = {}
            # Assign Values
            item ['variableSet']['id'] = vset['id']
            item ['variableSet']['name'] = vset['name']
            item ['variableSet']['type'] = 'VariableSet'
        if (filepolicy) and ((all_rules) or ('filePolicy' in item)):
            # Create FilePolicy
            item ['filePolicy'] = {}
            # Assign Values
            item ['filePolicy']['id'] = filepolicy['id']
            item ['filePolicy']['name'] = filepolicy['name']
            item ['filePolicy']['type'] = 'FilePolicy'

        # Delete Unprocessable items
        del item['links']
        del item['metadata']
        if 'commentHistoryList' in item:
            del item['commentHistoryList']
        if ('logFiles' in item) and ('filePolicy' not in item):
            del item['logFiles']

    if len(acp_rules) > 500:
        print(f'*\n*\nModifying a large number of rules, please be patient...\n')
    # Send PUT requests with a maximum 1000 items per request
    while len(acp_rules) !=0:
        if len(acp_rules) >= 1000:
            put_data = acp_rules[:1000]
            put_bulk_acp_rules(server,headers,username,password,API_UUID,acp['id'],put_data)
            acp_rules = acp_rules[1000:]
        else:
            put_data = acp_rules[:len(acp_rules)]
            put_bulk_acp_rules(server,headers,username,password,API_UUID,acp['id'],put_data)
            acp_rules = acp_rules[len(acp_rules):]



#
#
#
# Define Inventory List Script as Funtion
def get_inventory(server,headers,username,password):
    print ('''
***********************************************************************************************
*                           Pull Full FMC Device Inventory List                               *
*_____________________________________________________________________________________________*
*                                                                                             *
***********************************************************************************************
''')

    print('Generating Access Token')
    # Generate Access Token and pull domains from auth headers
    results=access_token(server,headers,username,password)
    headers['X-auth-access-token']=results[0]
    domains = results[1]

    if len(domains) > 1:
        API_UUID = select('Domain',domains)['uuid']
    else:
        API_UUID = domains[0]['uuid']

    # Get all Devices
    print('*\n*\nCOLLECTING ALL INVENTORY...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/devices/devicerecords?expanded=true&offset=0&limit=1000'
    DEVICELIST_DATA = get_items(url,headers)

    # Get all Cluster Devices
    print('*\n*\nCOLLECTING CLUSTER INVENTORY...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/deviceclusters/ftddevicecluster?expanded=true&offset=0&limit=1000'
    CLUSTER_DATA = get_items(url,headers)

    # Get all HA Devices
    print('*\n*\nCOLLECTING HA PAIR INVENTORY...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/devicehapairs/ftddevicehapairs?expanded=true&offset=0&limit=1000'
    HA_DATA = get_items(url,headers)


    ## TEST PRINT
    #print(json.dumps(DEVICELIST_DATA,indent=4))
    #print(json.dumps(CLUSTER_DATA,indent=4))
    #print(json.dumps(HA_DATA,indent=4))

    # Create Base Dict
    INVENTORY = {
        'deviceClusters':[],
        'deviceHAPairs':[],
        'devices':[]
        }

    if CLUSTER_DATA != []:
        for item in CLUSTER_DATA:
            temp_dict = {}
            temp_dict['name']= item['name']
            temp_dict['masterDevice'] = get_device_details(item['masterDevice']['id'],DEVICELIST_DATA)
            temp_dict['slaveDevices'] = []
            for item in item['slaveDevices']:
                temp_dict['slaveDevices'].append(get_device_details(item['id'],DEVICELIST_DATA))
            INVENTORY['deviceClusters'].append(temp_dict)

    if HA_DATA != []:
        for item in HA_DATA:
            temp_dict = {}
            temp_dict['name']= item['name']
            temp_dict['primary'] = get_device_details(item['primary']['id'],DEVICELIST_DATA)
            temp_dict['secondary'] = get_device_details(item['secondary']['id'],DEVICELIST_DATA)
            INVENTORY['deviceHAPairs'].append(temp_dict)

    if DEVICELIST_DATA != []:
        for item in DEVICELIST_DATA:
            temp_dict = {}
            temp_dict['name'] = item['name']
            temp_dict['model'] = item['model']
            temp_dict['hostname'] = item['hostName']
            temp_dict['healthStatus'] = item['healthStatus']
            temp_dict['sw_version'] = item['sw_version']
            temp_dict['license_caps'] = item['license_caps']
            temp_dict['ftdMode'] = ''
            if 'ftdMode' in item: temp_dict['ftdMode'] = item['ftdMode']
            temp_dict['deviceSerialNumber'] = ''
            if 'deviceSerialNumber' in item['metadata']: temp_dict['deviceSerialNumber'] = item['metadata']['deviceSerialNumber']
            if 'sruVersion' in item['metadata']: temp_dict['sru_version'] = item['metadata']['sruVersion']
            if 'vdbVersion' in item['metadata']: temp_dict['vdb_version'] = item['metadata']['vdbVersion']
            if 'snortVersion' in item['metadata']: temp_dict['snort_version'] = item['metadata']['snortVersion']
            if 'chassisData' in item['metadata']: temp_dict['chassisData'] = item['metadata']['chassisData']
            INVENTORY['devices'].append(temp_dict)


    print('*\n*\nFMC Inventory compilation successful...')
    # Ask if JSON output should be saved to File
    save = input('Would You Like To Save The JSON Output To File? [y/N]: ').lower()
    if save in (['yes','ye','y']):
        # Random Generated JSON Output File
        filename = ''.join(i for i in [chr(random.randint(97,122)) for i in range(6)])
        filename += '.json'
        print(f'*\n*\nRANDOM OUTPUT FILE CREATED... {filename}\n')
        with open(filename, 'a') as OutFile:
            OutFile.write(json.dumps(INVENTORY,indent=4))
    elif save in (['no','n','']):
        print(json.dumps(INVENTORY,indent=4))

    # Ask if CSV output should be saved to File
    save = input('Would You Like To Save CSV Output To File? [y/N]: ').lower()
    if save in (['yes','ye','y']):
        # Random Generated CSV Output File
        filename = ''.join(i for i in [chr(random.randint(97,122)) for i in range(6)])
        filename += '.csv'
        print(f'*\n*\nRANDOM OUTPUT FILE CREATED... {filename}\n')
        with open(filename, 'a') as OutFile:
            OutFile.write('NAME,MODEL,VERSION,STATUS,SERIAL,MODE,LICENSE,SRU,VDB,SNORT\n')
            if INVENTORY['deviceClusters'] != []:
                for item in INVENTORY['deviceClusters']:
                    mode = ''
                    sru_version = ''
                    vdb_version = ''
                    snort_version = ''
                    serial = ''
                    name = item['masterDevice']['name']
                    model = item['masterDevice']['model']
                    version = item['masterDevice']['sw_version']
                    status = item['masterDevice']['healthStatus']
                    license = ';'.join(item['masterDevice']['license_caps'])
                    if 'ftdMode' in item['masterDevice']: mode = item['masterDevice']['ftdMode']
                    if 'sru_version' in item['masterDevice']: sru_version = item['masterDevice']['sru_version']
                    if 'vdb_version' in item['masterDevice']: vdb_version = item['masterDevice']['vdb_version']
                    if 'snort_version' in item['masterDevice']: snort_version = item['masterDevice']['snort_version']
                    if 'chassisData' in item['masterDevice']: serial = item['masterDevice']['chassisData']['chassisSerialNo']
                    OutFile.write(f'{name},{model},{version},{status},{serial},{mode},{license},{sru_version},{vdb_version},{snort_version}\n')
                    for item in item['slaveDevices']:
                        mode = ''
                        sru_version = ''
                        vdb_version = ''
                        snort_version = ''
                        serial = ''
                        name = item['name']
                        model = item['model']
                        version = item['sw_version']
                        status = item['healthStatus']
                        license = ';'.join(item['license_caps'])
                        if 'ftdMode' in item: mode = item['ftdMode']
                        if 'sru_version' in item: sru_version = item['sru_version']
                        if 'vdb_version' in item: vdb_version = item['vdb_version']
                        if 'snort_version' in item: snort_version = item['snort_version']
                        if 'chassisData' in item: serial = item['chassisData']['chassisSerialNo']
                        OutFile.write(f'{name},{model},{version},{status},{serial},{mode},{license},{sru_version},{vdb_version},{snort_version}\n')
            if INVENTORY['deviceHAPairs'] != []:
                for item in INVENTORY['deviceHAPairs']:
                    mode = ''
                    sru_version = ''
                    vdb_version = ''
                    snort_version = ''
                    serial = ''
                    name = item['primary']['name']
                    model = item['primary']['model']
                    version = item['primary']['sw_version']
                    status = item['primary']['healthStatus']
                    license = ';'.join(item['primary']['license_caps'])
                    if 'ftdMode' in item['primary']: mode = item['primary']['ftdMode']
                    if 'sru_version' in item['primary']: sru_version = item['primary']['sru_version']
                    if 'vdb_version' in item['primary']: vdb_version = item['primary']['vdb_version']
                    if 'snort_version' in item['primary']: snort_version = item['primary']['snort_version']
                    if 'chassisData' in item['primary']:
                        serial = item['primary']['chassisData']['chassisSerialNo']
                    elif 'deviceSerialNumber' in item['primary']:
                        serial = item['primary']['deviceSerialNumber']
                    OutFile.write(f'{name},{model},{version},{status},{serial},{mode},{license},{sru_version},{vdb_version},{snort_version}\n')
                    mode = ''
                    sru_version = ''
                    vdb_version = ''
                    snort_version = ''
                    serial = ''
                    name = item['secondary']['name']
                    model = item['secondary']['model']
                    version = item['secondary']['sw_version']
                    status = item['secondary']['healthStatus']
                    license = ';'.join(item['secondary']['license_caps'])
                    if 'ftdMode' in item['secondary']: mode = item['secondary']['ftdMode']
                    if 'sru_version' in item['secondary']: sru_version = item['secondary']['sru_version']
                    if 'vdb_version' in item['secondary']: vdb_version = item['secondary']['vdb_version']
                    if 'snort_version' in item['secondary']: snort_version = item['secondary']['snort_version']
                    if 'chassisData' in item['secondary']:
                        serial = item['secondary']['chassisData']['chassisSerialNo']
                    elif 'deviceSerialNumber' in item['secondary']:
                        serial = item['secondary']['deviceSerialNumber']
                    OutFile.write(f'{name},{model},{version},{status},{serial},{mode},{license},{sru_version},{vdb_version},{snort_version}\n')
            if INVENTORY['devices'] != []:
                for item in INVENTORY['devices']:
                    serial = item['deviceSerialNumber']
                    name = item['name']
                    model = item['model']
                    hostname = item['hostname']
                    version = item['sw_version']
                    license = ';'.join(item['license_caps'])
                    status = item['healthStatus']
                    mode = ''
                    sru_version = ''
                    vdb_version = ''
                    snort_version = ''
                    serial = ''
                    if 'ftdMode' in item: mode = item['ftdMode']
                    if 'sru_version' in item: sru_version = item['sru_version']
                    if 'vdb_version' in item: vdb_version = item['vdb_version']
                    if 'snort_version' in item: snort_version = item['snort_version']
                    if 'chassisData' in item:
                        serial = item['chassisData']['chassisSerialNo']
                    elif 'deviceSerialNumber' in item:
                        serial = item['deviceSerialNumber']
                    OutFile.write(f'{name},{model},{version},{status},{serial},{mode},{license},{sru_version},{vdb_version},{snort_version}\n')





#
#
#
# Define Inventory List Script as Funtion
def register_ftd(server,headers,username,password):
    print ('''
***********************************************************************************************
*                                   Register FTD to FMC                                       *
*_____________________________________________________________________________________________*
*                                                                                             *
* USER INPUT NEEDED:                                                                          *
*                                                                                             *
*  1. FTD IP address                                                                          *
*                                                                                             *
*  2. FTD display name                                                                        *
*                                                                                             *
*  3. FTD CLI username and password                                                           *
*                                                                                             *
*  4. Select ACP to apply to FTD                                                              *
*                                                                                             *
***********************************************************************************************
''')

    print('Generating Access Token')
    # Generate Access Token and pull domains from auth headers
    results=access_token(server,headers,username,password)
    headers['X-auth-access-token']=results[0]
    domains = results[1]

    if len(domains) > 1:
        API_UUID = select('Domain',domains)['uuid']
    else:
        API_UUID = domains[0]['uuid']

    # Request FTD Details
    FTD_IP = input('Please enter FTD IP Address: ').strip()
    FTD_name = input('Please enter FTD display name: ').strip()
    FTD_user = input('Please enter FTD username: ').strip()
    FTD_pass = define_password()
    # Generate random Registration Key
    regKey = ''.join(i for i in [chr(random.randint(97,122)) for i in range(6)])

    # Create Get DATA JSON Dictionary to collect all ACP names
    print('*\n*\nCOLLECTING Access Policies...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/policy/accesspolicies?offset=0&limit=1000'
    acp_list = get_items(url,headers)
    if acp_list == []:
        print('*\n*\nNO ACCESS POLICY CONFIGURED...\nCREATE ACCESS POLICY IN FMC AND ATTEMPT AGAIN...')
        return
    acp = select('Access Control Policy',acp_list)
    #print(json.dumps(acp,indent=4))

    post_data = {
        'name': FTD_name,
        'hostName': FTD_IP,
        'natID': 'cisco123',
        'regKey': regKey,
        'type': 'Device',
        'license_caps': [
            'BASE',
            'MALWARE',
            'URLFilter',
            'THREAT'
        ],
        'accessPolicy': {
            'id': acp['id'],
            'type': 'AccessPolicy'
        }
    }


    url =f'{server}/api/fmc_config/v1/domain/{API_UUID}/devices/devicerecords'
    print(f'\nPerforming API POST to: {url}...\n')
    try:
        # REST call with SSL verification turned off:
        r = requests.post(url, data=json.dumps(post_data), headers=headers, verify=False)
        status_code = r.status_code
        resp = r.text
        print(f'Status code is: {status_code}')
        if status_code == 201 or status_code == 202:
            print('FMC Registration Post successful...')
            json_resp = r.json()
        else :
            r.raise_for_status()
            print (f'Error occurred in POST --> {resp}')
    except requests.exceptions.HTTPError as err:
        print (f'Error in connection --> {traceback.format_exc()}')
    finally:
        try:
            if r: r.close()
        except:
            None

    try:
        # Connect to FTD, and initiate registration
        print('\nConnecting to FTD for CLI registration...')
        connection = netmiko.ConnectHandler(ip=FTD_IP, device_type='autodetect', username=FTD_user, password=FTD_pass, global_delay_factor=6)
        output = connection.send_command(f'configure manager add {server.replace("https://","")} {regKey} cisco123')
        connection.disconnect()
        print('FTD Registration command successful...')
    except:
        print (f'Error in SSH connection --> {traceback.format_exc()}')
        connection.disconnect()



#
#
#
# Define Inventory List Script as Funtion
def prefilter_to_acp(server,headers,username,password):
    print ('''
***********************************************************************************************
*                    Convert Prefilter rules to Access-Control rules                          *
*_____________________________________________________________________________________________*
*                                                                                             *
* USER INPUT NEEDED:                                                                          *
*                                                                                             *
*  1. Select Access Policy                                                                    *
*                                                                                             *
*  2. Select Intrusion Policy and Variable Set to apply to ALL converted rules                *
*                                                                                             *
*  3. Select File Policy to apply to ALL converted rules                                      *
*                                                                                             *
***********************************************************************************************
''')

    print('Generating Access Token')
    # Generate Access Token and pull domains from auth headers
    results=access_token(server,headers,username,password)
    headers['X-auth-access-token']=results[0]
    domains = results[1]

    if len(domains) > 1:
        API_UUID = select('Domain',domains)['uuid']
    else:
        API_UUID = domains[0]['uuid']

    # Get all Access Control Policies
    print('*\n*\nCOLLECTING Access Policies...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/policy/accesspolicies?expanded=true&offset=0&limit=1000'
    acp_list = get_items(url,headers)

    acp = select('Access Control Policy',acp_list)
    #print(json.dumps(acp,indent=4))

    # Get Prefilter Policy
    print('*\n*\nCOLLECTING Applied Prefilter Policy...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/policy/prefilterpolicies/{acp["prefilterPolicySetting"]["id"]}/prefilterrules?expanded=true&offset=0&limit=1000'
    prefilter_list = get_items(url,headers)

    # Remove all 'TUNNEL' rules
    prefilter_list = [i for i in prefilter_list if i['ruleType'] != 'TUNNEL']

    if prefilter_list == []:
        print('*\n*\nNo Prefilter Rules available to migrate...')
        return

    # Get all Intrusion Policies
    print('*\n*\nCOLLECTING Intusion Policies...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/policy/intrusionpolicies?offset=0&limit=1000'
    ips_list = get_items(url,headers)
    # Add None option
    ips_list.append({'None':'None'})
    ips = select('Intusion Policy',ips_list)

    # Get all Variable Sets
    print('*\n*\nCOLLECTING Variable Sets...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/variablesets?offset=0&limit=1000'
    vset_list = get_items(url,headers)

    # Get Default Variable Set
    for item in vset_list:
        if item['name'] == 'Default-Set':
            default_vset = item

    # Select Variable Set for access rules
    if ips:
        vset = select('Variable Set',vset_list)
    else:
        vset = None

    # Get all File Policies
    print('*\n*\nCOLLECTING File Policies...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/policy/filepolicies?offset=0&limit=1000'
    file_list = get_items(url,headers)
    # Add None option
    file_list.append({'None':'None'})
    filepolicy = select('File Policy',file_list)
    #print(filepolicy)

    # Migrate prefilter rules to Access Rules
    print('*\n*\nConverting existing Prefilter rules to Access Rules...')
    acp_data = []
    DATE = datetime.now().strftime('%Y-%m-%d_%H%M')

    for item in prefilter_list:
        item['name']  =  f'Prefilter_{item["name"]}_{DATE}'
        if len(item['name']) > 50:
            item['newComments'] = [item['name']]
            item['name'] = item['name'][:50]
        if 'id' in item: del item['id']
        if 'metadata' in item: del item["metadata"]
        if 'links' in item: del item["links"]
        if 'bidirectional' in item: del item["bidirectional"]
        if 'sourceInterfaces' in item:
            item['sourceZones'] = item['sourceInterfaces']
            del item['sourceInterfaces']
        if 'destinationInterfaces' in item:
            item['destinationZones'] = item['destinationInterfaces']
            del item['destinationInterfaces']
        if 'bidirectional' in item: del item["bidirectional"]
        if (item['action'] == 'ANALYZE') and (item['ruleType'] !='TUNNEL'):
            item['logFiles'] = False
            item['action'] = 'ALLOW'
            item['type'] ='AccessRule'
            if ips:
                item['ipsPolicy'] = ips
                item['ipsPolicy']['type'] = 'IntrusionPolicy'
                item['variableSet'] = vset
                item['variableSet']['type'] = 'VariableSet'
            if filepolicy:
                item['logFiles'] = True
                item['sendEventsToFMC'] = True
                item['filePolicy'] = filepolicy
                item['filePolicy']['type'] = 'FilePolicy'
            del item['ruleType']
            acp_data.append(item)
        elif item['action'] =='BLOCK':
            item['logFiles'] = False
            item['type'] ='AccessRule'
            item['variableSet'] = default_vset
            del item["ruleType"]
            acp_data.append(item)
        elif item['action'] =='FASTPATH':
            item['logFiles'] = False
            item['logBegin'] = False
            item['action'] ='TRUST'
            item['type'] ='AccessRule'
            del item['ruleType']
            acp_data.append(item)



    # Post newly migrated access rules
    print('*\n*\nPosting new Access Rules...')
    url =f'{server}/api/fmc_config/v1/domain/{API_UUID}/policy/accesspolicies/{acp["id"]}/accessrules?bulk=true'
    print(f'\nPerforming API POST to: {url}...\n')
    try:
        # REST call with SSL verification turned off:
        r = requests.post(url, data=json.dumps(acp_data), headers=headers, verify=False)
        status_code = r.status_code
        resp = r.text
        print(f'Status code is: {status_code}')
        if status_code == 201 or status_code == 202:
            print('FMC Access Rules Post successful...')
        else :
            print (f'Error occurred in POST --> {resp}')
            r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print (f'Error in connection --> {traceback.format_exc()}')
    finally:
        try:
            if r: r.close()
        except:
            None




#
#
#
# Object Group Compare and Update
def obj_group_update(server,headers,username,password):
    print ('''
***********************************************************************************************
*                    Update Object Group with entries from txt file                           *
*_____________________________________________________________________________________________*
*                                                                                             *
* USER INPUT NEEDED:                                                                          *
*                                                                                             *
*  1. Object Group Name                                                                       *
*                                                                                             *
*  2. Network Text File                                                                       *
*                                                                                             *
*       Notes:                                                                                *
*          Supports groups with only IPv4 Host and Network objects                            *
*          Text file must contain only host IPs and networks with CIDR notation               *
*                                                                                             *
***********************************************************************************************
''')

    print('Generating Access Token')
    # Generate Access Token and pull domains from auth headers
    results=access_token(server,headers,username,password)
    headers['X-auth-access-token']=results[0]
    domains = results[1]

    if len(domains) > 1:
        API_UUID = select('Domain',domains)['uuid']
    else:
        API_UUID = domains[0]['uuid']

    objGroupName = input('Please Enter Object Group Name: ').strip()
    Test = False
    while not Test:
        # Request Input File
        read_file = input('Please Enter Input File /full/file/path.txt: ').strip()
        if os.path.isfile(read_file):
            # Read csv file
            open_read_file = open(read_file, 'r').read()
            Test = True
        else:
            print('MUST PROVIDE INPUT FILE...')

    fileEntries = open_read_file.splitlines()


    # Collect all Network objects
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/networks?expanded=true&offset=0&limit=1000'
    networks = get_items(url,headers)
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/hosts?expanded=true&offset=0&limit=1000'
    hosts = get_items(url,headers)



    url = f'{server}/api/fmc_config/v1/domain/e276abec-e0f2-11e3-8169-6d9ed49b625f/object/networkgroups?expanded=true&offset=0&limit=1000'
    objGroupEntries = []
    objGroups = get_items(url,headers)
    objGroup = None
    for g in objGroups:
        if g['name'] == objGroupName:
            objGroup = g

    if not objGroup:
        print(f'Group name "{objGroupName}" not found')
        return
    else:
        if 'literals' in objGroup:
            for lit in objGroup['literals']:
                if lit['type'] == 'Network':
                    objGroupEntries.append(IPv4Network(lit['value']).with_prefixlen)
                else:
                    objGroupEntries.append(lit['value'])
        if 'objects' in objGroup:
            # Append networks with CIDR notation
            objGroupEntries += [
                IPv4Network(item['value']).with_prefixlen for item in networks if item['id'] in [i['id'] for i in objGroup['objects']]]
            objGroupEntries += [
                item['value'] for item in hosts if item['id'] in [i['id'] for i in objGroup['objects']]]

        # Compile list of Missing entries on FMC
        diffMissing = [ip for ip in fileEntries if ip not in objGroupEntries]
        # Compile list of Extra entries on FMC
        diffExtra = [ip for ip in objGroupEntries if ip not in fileEntries]

        newLits = []
        newObjs = []
        newEntries = []
        # Include literals if they are in the file entries
        if 'literals' in objGroup:
            for lit in objGroup['literals']:
                if lit['type'] == 'Network':
                    if IPv4Network(lit['value']).with_prefixlen in fileEntries:
                        newEntries.append(IPv4Network(lit['value']).with_prefixlen)
                        newLits.append(lit)
                elif lit['value'] in fileEntries:
                    newEntries.append(lit['value'])
                    newLits.append(lit)

        for ip in fileEntries:
            if ('/' in ip) and (IPv4Network(ip).with_prefixlen not in newEntries):
                for net in networks:
                    try:
                        if IPv4Network(ip).with_prefixlen == IPv4Network(net['value']).with_prefixlen:
                            newObjs.append({
                                'type': net['type'],
                                'name': net['name'],
                                'id': net['id']
                            })
                            newEntries.append(IPv4Network(ip).with_prefixlen)
                    except:
                        None
            else:
                for host in hosts:
                    if (ip not in newEntries) and (ip == host['value']):
                        newObjs.append({
                            'type': host['type'],
                            'name': host['name'],
                            'id': host['id']
                        })
                        newEntries.append(ip)

        missingObj = [ip for ip in fileEntries if ip not in newEntries]

        createNets = {'data': [], 'result': []}
        createHosts = {'data': [], 'result': []}
        for ip in missingObj:
            if '/' in ip:
                createNets['data'].append({
                    'name': f'Net-{ip.replace("/","-")}',
                    'type': 'Network',
                    'description': '',
                    'value': ip
                })
            else:
                createHosts['data'].append({
                    'name': f'Host-{ip}',
                    'type': 'Host',
                    'description': '',
                    'value': ip
                })

        if createNets['data'] != []:
            # Post Network objects, and store JSON response with object uuids
            try:
                # REST call with SSL verification turned off:
                post_data = createNets['data']
                url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/networks?bulk=true'
                r = requests.post(url, data=json.dumps(post_data), headers=headers, verify=False)
                status_code = r.status_code
                resp = r.text
                print(f'Status code is: {status_code}')
                if status_code == 201 or status_code == 202:
                    print('Network Objects successfully created...')
                    createNets['result'] = r.json()['items']
                else :
                    print(f'Error occurred in POST --> {json.dumps(r.json(),indent=4)}')
                    r.raise_for_status()
            except requests.exceptions.HTTPError as err:
                print (f'Error in connection --> {traceback.format_exc()}')
            finally:
                try:
                    if r: r.close()
                except:
                    None

        if createHosts['data'] != []:
            # Post Host objects, and store JSON response with object uuids
            try:
                # REST call with SSL verification turned off:
                post_data = createHosts['data']
                url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/hosts?bulk=true'
                r = requests.post(url, data=json.dumps(post_data), headers=headers, verify=False)
                status_code = r.status_code
                resp = r.text
                print(f'Status code is: {status_code}')
                if status_code == 201 or status_code == 202:
                    print('Network Objects successfully created...')
                    createHosts['result'] = r.json()['items']
                else :
                    print(f'Error occurred in POST --> {json.dumps(r.json(),indent=4)}')
                    r.raise_for_status()
            except requests.exceptions.HTTPError as err:
                print (f'Error in connection --> {traceback.format_exc()}')
            finally:
                try:
                    if r: r.close()
                except:
                    None

        for net in createNets['result']:
            newObjs.append({
                'type': net['type'],
                'name': net['name'],
                'id': net['id']
            })

        for host in createHosts['result']:
            newObjs.append({
                'type': host['type'],
                'name': host['name'],
                'id': host['id']
            })

        # Update Object Group data
        del objGroup['links']
        del objGroup['metadata']
        objGroup['objects'] = newObjs
        objGroup['literals'] = newLits

        # PUT object group
        try:
            # REST call with SSL verification turned off:
            post_data = objGroup
            url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/object/networkgroups/{objGroup["id"]}'
            r = requests.put(url, data=json.dumps(post_data), headers=headers, verify=False)
            status_code = r.status_code
            resp = r.text
            print(f'Status code is: {status_code}')
            if status_code == 200:
                print('Network Object Group successfully updated...')
            else :
                print(f'Error occurred in PUT --> {json.dumps(r.json(),indent=4)}')
                r.raise_for_status()
        except requests.exceptions.HTTPError as err:
            print (f'Error in connection --> {traceback.format_exc()}')
        finally:
            try:
                if r: r.close()
            except:
                None

        # Print report
        print(f'Objects added to group:\n{json.dumps(diffMissing,indent=4)}')
        print(f'Objects removed from group:\n{json.dumps(diffExtra,indent=4)}')




#
#
#
# Export ACP and Prefilter Rules
def export_acp_rules(server,headers,username,password):
    print ('''
***********************************************************************************************
*                      Export ACP and Prefilter Rules to CSV file                             *
*_____________________________________________________________________________________________*
*                                                                                             *
***********************************************************************************************
''')

    outfile = open(f'acp_rule_export_{datetime.now().strftime("%Y-%m-%d_%H%M")}.csv','w')
    outfile.write('FMC_NAME,ACP_NAME,ACP_TYPE,ACP_ID,R_NAME,R_ID,R_ACTION,R_SRC_ZN,R_DST_ZN,R_SRC_IP,R_DST_IP,R_VLAN,R_USERS,R_APP,R_URL,R_SRC_P,R_DST_P,R_SRC_SGT,R_DST_SGT,R_IPS,R_FILE\n')

    FMC_NAME = server.replace('https://','')

    print('Generating Access Token')
    # Generate Access Token and pull domains from auth headers
    results=access_token(server,headers,username,password)
    headers['X-auth-access-token']=results[0]
    domains = results[1]

    if len(domains) > 1:
        API_UUID = select('Domain',domains)['uuid']
    else:
        API_UUID = domains[0]['uuid']

    # Get all Access Control Policies
    print('*\n*\nCOLLECTING Access Policies...')
    url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/policy/accesspolicies?expanded=true&offset=0&limit=1000'
    acp_list = get_items(url,headers)

    for acp in acp_list:
        url = f'{acp["rules"]["links"]["self"]}?expanded=true&offset=0&limit=1000'
        rules = get_items(url,headers)
        for rule in rules:
            temp_list = parse_rule(FMC_NAME,rule)
            outfile.write(f'{",".join(temp_list)}\n')

        # GET PREFILTER RULES ALSO
        # Get Prefilter Policy
        print('*\n*\nCOLLECTING Applied Prefilter Policy...')
        url = f'{server}/api/fmc_config/v1/domain/{API_UUID}/policy/prefilterpolicies/{acp["prefilterPolicySetting"]["id"]}/prefilterrules?expanded=true&offset=0&limit=1000'
        prefilter_rules = get_items(url,headers)
        for rule in prefilter_rules:
            temp_list = parse_rule(FMC_NAME,rule)
            outfile.write(f'{",".join(temp_list)}\n')

    outfile.close()



#
#
#
# Run Script if main
if __name__ == "__main__":
    #
    #
    #
    # Initial input request
    print ('''
***********************************************************************************************
*                                                                                             *
*                   Cisco FMC v6.7 API Tools (Written for Python 3.6+)                        *
*                                                                                             *
***********************************************************************************************
*                                                                                             *
* USER INPUT NEEDED:                                                                          *
*                                                                                             *
*  1. FQDN for FMC server (hostname.domain.com)                                               *
*                                                                                             *
*  2. API Username                                                                            *
*                                                                                             *
*  3. API Password                                                                            *
*                                                                                             *
***********************************************************************************************
''')

    Test = False
    while not Test:
        # Request FMC server FQDN
        server = input('Please Enter FMC fqdn: ').lower().strip()

        # Validate FQDN
        if server[-1] == '/':
            server = server[:-1]
        if '//' in server:
            server = server.split('//')[-1]

        # Perform Test Connection To FQDN
        s = socket.socket()
        print(f'Attempting to connect to {server} on port 443')
        try:
            s.connect((server, 443))
            print(f'Connecton successful to {server} on port 443')
            Test = True
        except:
            print(f'Connection to {server} on port 443 failed: {traceback.format_exc()}\n\n')

    # Adding HTTPS to Server for URL
    server = f'https://{server}'
    headers = {'Content-Type': 'application/json','Accept': 'application/json'}

    # Request Username and Password without showing password in clear text
    username = input('Please Enter API Username: ').strip()
    password = define_password()
    print ('''
***********************************************************************************************
*                                                                                             *
* TOOLS AVAILABLE:                                                                            *
*                                                                                             *
*  1. Basic URL GET                                                                           *
*                                                                                             *
*  2. Create Network-Objects in bulk                                                          *
*                                                                                             *
*  3. Create Network-Objects in bulk and add to New Object-Group                              *
*                                                                                             *
*  4. Update IPS and/or File Policy for Access Rules                                          *
*                                                                                             *
*  5. Get Inventory List from FMC                                                             *
*                                                                                             *
*  6. Register FTD to FMC                                                                     *
*                                                                                             *
*  7. Migrate Prefilter rules to Access Rules                                                 *
*                                                                                             *
*  8. Update Object Group with entries from txt file                                          *
*                                                                                             *
*  9. Export ACP and Prefilter Rules to CSV file                                              *
*                                                                                             *
***********************************************************************************************
''')

    #
    #
    #
    # Run script until user cancels
    while True:
        Script = False
        while not Script:
            script = input('Please Select Tool: ')
            if script == '1':
                Script = True
                blank_get(server,headers,username,password)
            elif script == '2':
                Script = True
                post_network_object(server,headers,username,password)
            elif script == '3':
                Script = True
                post_network_object_group(server,headers,username,password)
            elif script == '4':
                Script = True
                put_intrusion_file(server,headers,username,password)
            elif script == '5':
                Script = True
                get_inventory(server,headers,username,password)
            elif script == '6':
                Script = True
                register_ftd(server,headers,username,password)
            elif script == '7':
                Script = True
                prefilter_to_acp(server,headers,username,password)
            elif script == '8':
                Script = True
                obj_group_update(server,headers,username,password)
            elif script == '9':
                Script = True
                export_acp_rules(server,headers,username,password)
            else:
                print('INVALID ENTRY... ')

        # Ask to end the loop
        print ('''
***********************************************************************************************
*                                                                                             *
* TOOLS AVAILABLE:                                                                            *
*                                                                                             *
*  1. Basic URL GET                                                                           *
*                                                                                             *
*  2. Create Network-Objects in bulk                                                          *
*                                                                                             *
*  3. Create Network-Objects in bulk and add to New Object-Group                              *
*                                                                                             *
*  4. Update IPS and/or File Policy for Access Rules                                          *
*                                                                                             *
*  5. Get Inventory List from FMC                                                             *
*                                                                                             *
*  6. Register FTD to FMC                                                                     *
*                                                                                             *
*  7. Migrate Prefilter rules to Access Rules                                                 *
*                                                                                             *
*  8. Update Object Group with entries from txt file                                          *
*                                                                                             *
*  9. Export ACP and Prefilter Rules to CSV file                                              *
*                                                                                             *
***********************************************************************************************
''')
        Loop = input('*\n*\nWould You Like To use another tool? [y/N]').lower()
        if Loop not in (['yes','ye','y','1','2','3','4','5','6','7','8','9']):
            break
