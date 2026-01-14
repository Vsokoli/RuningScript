import sys
import os
import traceback
import re
from lxml import etree as lxml
import requests
import json
import datetime


def check_print_file():
    def get_params():
        params_dictx = {}
        try:
            for ccParam in sys.argv:
                if re.search('(?i)^--filePrep_jobPath-.+$', ccParam):
                    params_dictx['filePrep_jobPath'] = re.search('(?i)^(--filePrep_jobPath-)(.+)$', ccParam).group(2)
                elif re.search('(?i)^--location-.+$', ccParam):
                    params_dictx['location'] = re.search('(?i)^(--location-)(.+)$', ccParam).group(2)
        except Exception as exc:
            tb = traceback.format_exc()
            sys.stderr.write('Exception Parameter readin\n')
            print(tb)
            sys.exit(-2)

        print(params_dictx)
        if len(params_dictx) != 2:
            sys.stderr.write('Error : Parameter length - aborting\n')
            sys.exit(-2)
        return params_dictx

    def get_job_path(params_dictx):
        re_pattern_lst = {
            'orderId': re.compile('(?i)^[a-z]{2}[0-9]{6,}X[0-9]{2}$'),
            'sheetId': re.compile(r'(?i)^(?<!\d)\d{10,11}(?!\d)$'),
            'sym_sheet': re.compile(r'(?i)^SYM[0-9]{7,8}$')
        }

        nas_homex = fr"\\datenpool-{params_dictx['location']}.druckhaus.local"
        JobID = params_dictx['JobID']
        location = params_dictx['location']

        order_type = [ccPatternName for ccPatternName, ccPatternValue in re_pattern_lst.items()
                      if re.search(ccPatternValue, JobID)]
        if len(order_type) != 1:
            sys.stderr.write('Error : JobID not recognized, invalid JobID\n')
            sys.exit(-3)

        type_path_pattern = {
            'orderId': fr"{nas_homex}\FSH-JOBS-{location}\{JobID[0:7]}XXXXXX\{JobID}",
            'sheetId': fr"{nas_homex}\FSH-DRUCKBOGEN-{location}\{JobID[0:5]}XXX\{JobID}",
            'sym_sheet': fr"{nas_homex}\FSH-JOBS-{location}\{JobID[0:8]}XX\{JobID}"
        }

        JOB_TYPE = order_type[0]
        if JOB_TYPE not in type_path_pattern:
            sys.stderr.write(f'Error : JobID type {JOB_TYPE} not recognized\n')
            sys.exit(-4)

        return type_path_pattern[order_type[0]], order_type[0]

    def check_if_job_in_ptkdb(params_dictx, JOB_TYPE):
        tmp_job_type = {'orderId': 'singleorder', 'sheetId': 'sheetorder'}[JOB_TYPE]
        job_id = params_dictx['JobID']

        ptk_type = 'archiv'
        if re.search('(?i)^DE9|^2\d+', job_id):
            ptk_type = 'stg'

        base_url = f"https://printtalk.{ptk_type}.faip.io/v2/api/rest/production"
        headers = { 'x-api-key': 'ChM1JDVu47cKTvG3j90OSP658qPLV2' }

        try:
            final_url = f'{base_url}/{tmp_job_type}?jobID={job_id}'
            r = requests.get(final_url, headers=headers, verify=False)

            if r.status_code == 200:
                print("Job Exists")
                return True
            else:
                print(f"Attempt failed with status {r.status_code}")
        except Exception as e:
            print(f"Request failed with exception: {e}")

        print("Job does not exist in database.")
        return False

    # # #
    # #
    #

    print(sys.argv)
    params_dictx = get_params()

    with open(params_dictx['filePrep_jobPath'], encoding='UTF-8') as ff:
        filePrep_parsed = lxml.fromstring(ff.read().encode('UTF-8'))
    params_dictx['JobID'] = filePrep_parsed.find('.').attrib['JobID']

    job_base_path, JOB_TYPE = get_job_path(params_dictx)
    check_file_list = []

    ptk_file_path = f"{job_base_path}\\originale\\{params_dictx['JobID']}.ptk"
    check_file_list.append({'ProductPart': 'JobPTK', 'filePath': ptk_file_path})

    if os.path.isfile(ptk_file_path):
        with open(ptk_file_path, encoding='UTF-8') as ff:
            ptk_parsed = lxml.fromstring(ff.read().encode('UTF-8'))
        nsx = {'ptk': 'http://www.printtalk.org/schema_2_0', 'xjdf': 'http://www.CIP4.org/JDFSchema_2_0'}

        pdf_resource = ptk_parsed.find(
            "./ptk:Request/ptk:PurchaseOrder/xjdf:XJDF/xjdf:ResourceSet[@Name='RunList'][@Usage='Input']",
            namespaces=nsx)

        for ccResNode in pdf_resource:
            tmp_dictx = {'ProductPart': ccResNode.find('./xjdf:Part', namespaces=nsx).attrib.get('ProductPart', 'Not Found')}
            tmp_url = ccResNode.find('./xjdf:RunList/xjdf:FileSpec', namespaces=nsx).attrib.get('URL', 'Not Found')
            tmp_dictx['filePath'] = os.path.join(fr"{job_base_path}\originale", os.path.basename(tmp_url))
            check_file_list.append(tmp_dictx)

    exit_map = {True: 0, False: 1}
    print('List to check : = ', check_file_list)
    file_check_dict = {ccDict['ProductPart']: os.path.isfile(ccDict['filePath']) for ccDict in check_file_list}
    if not all(file_check_dict.values()):
        sys.stderr.write('Error : At least one file does not exist : ' + str(file_check_dict) + '\n')
        sys.exit(exit_map[False])
    else:
        # VERIFY IF THE JOB IN THE DATABASE EXISTS BEFORE EXIT
        job_is_registered = check_if_job_in_ptkdb(params_dictx, JOB_TYPE)
        if not job_is_registered:
            sys.stderr.write(f'Error: Job {params_dictx["JobID"]} not found in PTK database\n')
            sys.exit(exit_map[False])

        sys.exit(exit_map[True])


if __name__ == '__main__':
    print('Full argv : \n', sys.argv, '\n')
    if len(str(os.path.dirname(sys.argv[0]))) > 1 and len(str(os.path.dirname(os.path.realpath(__file__)))) > 1:
        pgdirx = os.path.dirname(sys.argv[0])
    else:
        pgdirx = os.path.dirname(os.path.realpath(__file__))

    check_print_file()

    sys.exit(-2)
