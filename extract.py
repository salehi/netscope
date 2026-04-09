from io import TextIOWrapper

import maxminddb

db = maxminddb.open_database('GeoLite2-Country.mmdb')
all_iso_codes = set()
for _, data in db:
    iso_code = data.get('registered_country', {}).get('iso_code', None)
    if type(iso_code) is str:
        name_en = data.get('registered_country')['names']['en']
        all_iso_codes.add(iso_code)
    else:
        iso_code = data.get('country', {}).get('iso_code', None)
        if type(iso_code) is str:
            name_en = data.get('country')['names']['en']
            all_iso_codes.add(iso_code)
        else:
            pass
del _

CC_FILE: dict[str, TextIOWrapper] = {}
for item in all_iso_codes:
    CC_FILE[item] = open(f'Countries/{item}.txt', 'w')

for network, data in db:
    iso_code = data.get('registered_country', {}).get('iso_code', None)
    if iso_code is None:
        iso_code = data.get('country', {}).get('iso_code', None)
        if iso_code is None:
            db.close()
            raise Exception(f"No iso_code for {network}")
    if iso_code in CC_FILE.keys():
        CC_FILE[iso_code].write(f'{network}\t{iso_code}\n')
        CC_FILE[iso_code].flush()

db.close()
for k, v in CC_FILE.items():
    v.close()
