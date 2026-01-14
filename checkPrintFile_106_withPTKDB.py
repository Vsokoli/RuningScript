import shutil
import sys
import os
import time
import traceback
import re
from lxml import etree as lxml
import requests 
#test test

# import shutil


def check_print_file():
    def get_params():
        params_dictx = {}
        try:
            for ccParam in sys.argv:
                if re.search('(?i)^--filePrep_jobPath-.+$', ccParam):
                    params_dictx['filePrep_jobPath'] = re.search('(?i)^(--filePrep_jobPath-)(.+)$', ccParam).group(2)
                elif re.search('(?i)^--current_location-.+$', ccParam):
                    params_dictx['current_location'] = re.search('(?i)^(--current_location-)(.+)$', ccParam).group(2)
        except Exception as exc:
            tb = traceback.format_exc()
            sys.stderr.write('Exception Parameter readin')
            print(tb)
            sys.exit(-2)

        print(params_dictx)
        if len(params_dictx) != 2:
            sys.stderr.write('Error : Parameter length - aborting')
            sys.exit(-2)
        return params_dictx

    def get_job_path(params_dictx, location):
        loc_nas_map = {'EKE': 'KE', 'DKE': 'KE',}
        loc_nas_map.update({'EDB': 'DB', 'DMD': 'DB'})
        loc_nas_map.update({'EHE': 'MAR', 'DHE': 'MAR', 'EMN': 'MAR', 'DMN': 'MAR'})
        loc_nas_map.update({'EKL': 'KH', 'DKL': 'KH'})

        re_pattern_lst = {'orderId': re.compile('(?i)^[a-z]{2}[0-9]{6,}X[0-9]{2}$'),
            'sheetId': re.compile(r'(?i)^(?<!\d)\d{10,11}(?!\d)$'),
            'sym_sheet': re.compile(r'(?i)^SYM[0-9]{7,8}$')}

        nas_homex = fr"{location_map[location]}"
        JobID = params_dictx['JobID']

        order_type = [ccPatternName for ccPatternName, ccPatternValue in re_pattern_lst.items() if re.search(ccPatternValue, JobID)]
        if len(order_type) != 1:
            sys.stderr.write('Error : JobID not recognized, invalid JobID')
            sys.exit(-3)

        type_path_pattern = {}
        type_path_pattern['orderId'] = fr"{nas_homex}\FSH-JOBS-{loc_nas_map[location]}\{JobID[0:7]}XXXXXX\{JobID}"
        type_path_pattern['sheetId'] = fr"{nas_homex}\FSH-DRUCKBOGEN-{loc_nas_map[location]}\{JobID[0:5]}XXX\{JobID}"
        type_path_pattern['sym_sheet'] = fr"{nas_homex}\FSH-JOBS-{loc_nas_map[location]}\{JobID[0:8]}XX\{JobID}"

        return type_path_pattern[order_type[0]]

    def sym_sheet_adjust(params_dictx=None, ptk_parsed=None, filePrep_parsed=None):

        tmp_url = f"FA-SIG-{params_dictx['JobID']}.pdf"
        filePrep_parsed.xpath("./ResourceSet[@Name='RunList'][@Usage='Input']/Resource/RunList/FileSpec")[0].attrib['URL'] = tmp_url

        # write back
        treex = lxml.ElementTree(ptk_parsed)
        treex.write(f"{params_dictx['ptk_file_path']}", xml_declaration=True, encoding='UTF-8', method="xml")

        treex = lxml.ElementTree(filePrep_parsed)
        treex.write(f"{params_dictx['filePrep_jobPath']}", xml_declaration=True, encoding='UTF-8', method="xml")

    # determine job type (orderId / sheetId / sym_sheet) 
    def get_job_type(JobID):
        re_pattern_lst = {
            'orderId': re.compile('(?i)^[a-z]{2}[0-9]{6,}X[0-9]{2}$'),
            'sheetId': re.compile(r'(?i)^(?<!\d)\d{10,11}(?!\d)$'),
            'sym_sheet': re.compile(r'(?i)^SYM[0-9]{7,8}$')
        }
        order_type = [name for name, patt in re_pattern_lst.items() if re.search(patt, JobID)]
        if len(order_type) != 1:
            sys.stderr.write('Error : JobID not recognized, invalid JobID')
            sys.exit(-3)
        return order_type[0]

    # PTK database check (API)
    def check_if_job_in_ptkdb(params_dictx, JOB_TYPE):
        if JOB_TYPE == 'orderId':
            api_endpoint = "singleorder"
        else:
            # sheetId and sym_sheet -> sheet
            api_endpoint = "sheet"

        base_url = "https://printtalk.archiv.faip.io/api/rest/production"
        job_id = params_dictx['JobID']

        headers = {
            'x-api-key': 'ChM1JDVu47cKTvG3j90OSP658qPLV2'
        }

        try:
            
            final_url = f'{base_url}/{api_endpoint}?JobID={job_id}'
            r = requests.get(final_url, headers=headers, verify=False)

            if r.status_code == 200:
                print("Job Exists in PTK database")
                return True
            else:
                print(f"Attempt failed with status {r.status_code}")
        except Exception as e:
            print(f"Request failed with exception: {e}")

        print("Job does not exist in PTK database.")
        return False


    # # #
    # #
    #

    print(sys.argv)

    location_map = {'EKE': r'\\datenpool-ke.druckhaus.local', 'DKE': r'\\datenpool-ke.druckhaus.local'}
    location_map.update({'EDB': r'\\datenpool-db.druckhaus.local', 'DMD': r'\\datenpool-db.druckhaus.local'})
    location_map.update({'EHE': r'\\datenpool-mar.druckhaus.local', 'DHE': r'\\datenpool-mar.druckhaus.local'})
    location_map.update({'EMN': r'\\datenpool-mar.druckhaus.local', 'DMN': r'\\datenpool-mar.druckhaus.local'})
    location_map.update({'EKL': r'\\datenpool-kh.druckhaus.local', 'DKL': r'\\datenpool-kh.druckhaus.local'})

    params_dictx = get_params()

    with open(params_dictx['filePrep_jobPath'], encoding='UTF-8') as ff:
        filePrep_parsed = lxml.fromstring(ff.read().encode('UTF-8'))
    params_dictx['JobID'] = filePrep_parsed.find('.').attrib['JobID']

    params_dictx['src_job_path'] = get_job_path(params_dictx, filePrep_parsed.find('./GeneralID[@IDUsage="Location"]').attrib.get('IDValue', None))
    params_dictx['dst_job_path'] = get_job_path(params_dictx, params_dictx['current_location'])

    params_dictx['adjust_sym_sheet'] = False

    check_file_list = []
    params_dictx['ptk_file_path'] = f"{params_dictx['src_job_path']}\\originale\\{params_dictx['JobID']}.ptk"
    check_file_list.append({'ProductPart': 'JobPTK', 'filePath': params_dictx['ptk_file_path']})

    if os.path.isfile(params_dictx['ptk_file_path']):
        with open(params_dictx['ptk_file_path'], encoding='UTF-8') as ff:
            ptk_parsed = lxml.fromstring(ff.read().encode('UTF-8'))
        nsx = {'ptk': 'http://www.printtalk.org/schema_2_0', 'xjdf': 'http://www.CIP4.org/JDFSchema_2_0'}

        xjdf_node = ptk_parsed.find("./ptk:Request/ptk:PurchaseOrder/xjdf:XJDF", namespaces=nsx)
        printing_type = re.search('(?i)DigitalPrinting|ConventionalPrinting', xjdf_node.attrib.get('Types')).group(0)

        pdf_res_lst = []
        pdf_res_lst.append(xjdf_node.xpath(f"./xjdf:ResourceSet[@Name='RunList'][@ProcessUsage='DigitalPrinting']/xjdf:Resource", namespaces=nsx))
        pdf_res_lst.append(xjdf_node.xpath(f"./xjdf:ResourceSet[@Name='RunList'][@ProcessUsage='ConventionalPrinting']/xjdf:Resource", namespaces=nsx))

        if len([lst[0] for lst in pdf_res_lst if len(lst) > 0]) == 0:
            pdf_resource = xjdf_node.xpath(f"./xjdf:ResourceSet[@Name='RunList'][@Usage='Input']/xjdf:Resource", namespaces=nsx)
        else:
            pdf_resource = [lst[0] for lst in pdf_res_lst if len(lst) > 0]
        if not pdf_resource:
            print('Error : Keine Passende Resource Node gefunden mit entsprechendem printing type = ', printing_type)
            sys.exit(1)

        intent_map = {'body': 'inner'}
        tmp_intent = filePrep_parsed.find('./GeneralID[@IDUsage="PreparationIntent"]')
        if tmp_intent is not None:
            tmp_intent = intent_map.get(tmp_intent.attrib.get('IDValue', None).lower(), tmp_intent.attrib.get('IDValue', None).lower())

        for ccResNode in pdf_resource:
            prod_part = ccResNode.find('./xjdf:Part', namespaces=nsx)
            prod_part = prod_part.get('ProductPart', 'Not Found') if prod_part is not None else 'Not found'

            if tmp_intent is None or tmp_intent.lower() == 'product' or re.search(rf'(?i){tmp_intent}', prod_part):
                tmp_dictx = {'ProductPart': prod_part}
                tmp_url = ccResNode.find('./xjdf:RunList/xjdf:FileSpec', namespaces=nsx).attrib.get('URL', 'Not Found')

                if re.search(r'(?i)^SYM[0-9]{7,8}$', params_dictx['JobID']):
                    params_dictx['adjust_sym_sheet'] = True
                    tmp_url = f"FA-SIG-{params_dictx['JobID']}.pdf"
                    ccResNode.find('./xjdf:RunList/xjdf:FileSpec', namespaces=nsx).attrib['URL'] = tmp_url

                tmp_dictx['filePath'] = os.path.join(fr"{params_dictx['src_job_path']}\originale", os.path.basename(tmp_url))
                check_file_list.append(tmp_dictx)

        print('Original files to check : = ', check_file_list)
        file_check_dict = {ccDict['ProductPart']: os.path.isfile(ccDict['filePath']) for ccDict in check_file_list}
        if not all(file_check_dict.values()):
            sys.stderr.write('Error origin check : At least one file of the source does not exist : ' + str(file_check_dict))
            sys.exit(1)

        print(f'all origin files found > checking destination > {params_dictx["current_location"]}')

        for ccCheckFile in check_file_list:
            tmp_dst_file_path = fr"{params_dictx['dst_job_path']}\originale\{os.path.basename(ccCheckFile['filePath'])}"
            print(f'>> checking > {tmp_dst_file_path}')
            if not os.path.isfile(tmp_dst_file_path):
                if not os.path.isdir(os.path.dirname(tmp_dst_file_path)):
                    os.makedirs(os.path.dirname(tmp_dst_file_path))
                print(f'>> copying {tmp_dst_file_path}')
                shutil.copy2(ccCheckFile['filePath'], tmp_dst_file_path)

        # After files are OK and copied, verify job in PTK database 
        job_type_raw = get_job_type(params_dictx['JobID'])
        job_is_registered = check_if_job_in_ptkdb(params_dictx, job_type_raw)
        if not job_is_registered:
            sys.stderr.write(f'Error: Job {params_dictx["JobID"]} not found in PTK database')
            sys.exit(1)

    else:
        print('Error : PTK not found > : = ', params_dictx['ptk_file_path'])
        sys.exit(1)

    if params_dictx['adjust_sym_sheet']:
        sym_sheet_adjust(params_dictx=params_dictx, ptk_parsed=ptk_parsed, filePrep_parsed=filePrep_parsed)

    sys.exit(0)


if __name__ == '__main__':
    print('Full argv : \n', sys.argv, '\n')
    if len(str(os.path.dirname(sys.argv[0]))) > 1 and len(str(os.path.dirname(os.path.realpath(__file__)))) > 1:
        pgdirx = os.path.dirname(sys.argv[0])
    else:
        pgdirx = os.path.dirname(os.path.realpath(__file__))

    check_print_file()

    sys.exit(-2)


#  JobID ## re.compile(r'(?i)[a-z]{2}[0-9]{6,}X[0-9]{2}|(?<!\d)\d{10,11}(?!\d)')
