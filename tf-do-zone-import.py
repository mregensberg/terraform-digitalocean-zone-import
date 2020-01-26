#! /usr/bin/env python3

import requests
import sys
import os
import pprint

# for a given endpoint and access token, return the zone structure as json
def do_fetch(endpoint, pat):
    headers = {"Authorization": "Bearer "+pat}
    response = requests.get(endpoint, headers=headers)
    return(response.json())

# different records differ. differently.
def render_mx(record):
    result = {
        'domain': 'digitalocean_domain.'+TF_ZONE_NAME+'.name',
        'name': '"'+record['name']+'"',
        'type': '"MX"',
        'priority': record['priority'],
        'value': '"'+record['data']+'"',
        'ttl': record['ttl']
    }
    return(result)

# yosafbridge.
def render_generic(record):
    result = {
        'domain': 'digitalocean_domain.'+TF_ZONE_NAME+'.name',
        'name': '"'+record['name']+'"',
        'type': '"'+record['type']+'"',
        'value': '"'+record['data']+'"',
        'ttl': record['ttl']
    }
    return(result)

# do a bunch of things so the generated resource names are
# (a) unique, (b) not too ugly and (c) consistent for the state import
def format_rendered_record(rendered_record, type, iter):
    result = 'resource "digitalocean_record" "'+build_resource_name(type, iter)+'" {\n'
    for key, value in rendered_record.items():
        result += '  '+key+' = '+str(value)+'\n'
    result += '}\n\n'
    return(result)

def build_resource_name(type, iter):
    r = TF_ZONE_NAME+'_'+type+str(iter)
    return(r.lower())

def find_or_update(record_names, record):
    record_type = record['type']
    if record_type in record_names:
        record_names[record_type] += 1
    else:
        record_names[record_type] = 1
    return(record_names)


##### main #############
# check we have a domain
if len(sys.argv) < 2:
    print('Usage:', sys.argv[0], 'mydomain.com [-d]')
    sys.exit(1)
else:
    ZONE_NAME = sys.argv[1]
    TF_ZONE_NAME = ZONE_NAME.replace(".","_")
    TF_FILE = ZONE_NAME.replace(".","_") + ".tf"
    TF_STATE_FILE = ZONE_NAME.replace(".","_") + "_import.sh"

# barf some json if we need to
if '-d' in sys.argv:
    DEBUG = True
else:
    DEBUG = False

# check we have a token and set the endpoint
DO_PAT = os.environ.get('DO_PAT')
DO_ENDPOINT = os.environ.get('DO_ENDPOINT') or 'https://api.digitalocean.com/v2/domains/'+ZONE_NAME+'/records'
if not DO_PAT:
    print("Missing Digitalocean personal access token. Please set a DO_PAT environment variable.")
    print("Example: export DO_PAT=\"PERSONAL_ACCESS_TOKEN\"")
    sys.exit(1)
else:
    print("DO_PAT:", DO_PAT[:3]+"****"+DO_PAT[-3:])
    print("DO_ENDPOINT: ", DO_ENDPOINT)

# basic sanity check, errors and the json return if requested
domain = do_fetch(DO_ENDPOINT, DO_PAT)
if 'message' in domain:
    print('Error:', domain['message'])
    sys.exit(1)

if DEBUG:
    pp = pprint.PrettyPrinter(indent=2)
    pp.pprint(domain['domain_records'])

# if we got this far, we might have a file.
# gather some IDs as we go for the state importer
ids = {}
with open(TF_FILE, "w") as f:
    numBytes = 0
    # add the resource domain
    f.write("resource \"digitalocean_domain\" \""+TF_ZONE_NAME+"\" {\n")
    f.write("  name = \""+ZONE_NAME+"\"\n")
    f.write("}\n\n")

    record_names = {}
    for record in domain['domain_records']:
        # resource names in tf need to be unique (within the module)
        # so keep a record of type iterations
        record_names = find_or_update(record_names, record)
        # ...and set the count
        iter = record_names[record['type']]
        if record['type'] == 'MX':
            f.write(format_rendered_record(render_mx(record), record['type'], iter))
        else:
            f.write(format_rendered_record(render_generic(record), record['type'], iter))

        # used for the state import - we need the ID, along with the resource name
        id = record['id']
        resource_name = build_resource_name(record['type'], iter)
        ids[id] = resource_name
f.close()

with open(TF_STATE_FILE, "w") as f:
    for key, value in ids.items():
        f.write('terraform import digitalocean_record.'+value+' '+ZONE_NAME+','+str(key)+'\n')
f.close()
