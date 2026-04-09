import maxminddb

db = maxminddb.open_database('GeoLite2-Country.mmdb')
all_iso_codes = set()
for network, data in db:
    iso_code = data.get('registered_country',{}).get('iso_code',None)
    if type(iso_code) is str:
        name_en = data.get('registered_country')['names']['en']
        all_iso_codes.add((iso_code, name_en))
    else:
        iso_code = data.get('country',{}).get('iso_code',None)
        if type(iso_code) is str:
            name_en = data.get('country')['names']['en']
            all_iso_codes.add((iso_code, name_en))
        else:
            pass
with open('country_list.txt', 'w') as f:
    for iso_code, name_en in sorted(all_iso_codes):
            f.write(f"{iso_code},{name_en}\n")
