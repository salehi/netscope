import argparse
import json

import maxminddb


def get_data(ip):
    db_asn = maxminddb.open_database("./GeoLite2-ASN.mmdb")
    db_city = maxminddb.open_database("./GeoLite2-City.mmdb")
    db_country = maxminddb.open_database("./GeoLite2-Country.mmdb")

    return {
        "ASN": db_asn.get(ip),
        "City": db_city.get(ip),
        "Country": db_country.get(ip),
    }


def main():
    parser = argparse.ArgumentParser(description="Check IP info using MaxMind DB")
    parser.add_argument('-ip', type=str, required=True, help="IP address to look up")
    args = parser.parse_args()
    data = get_data(args.ip)
    print(json.dumps(data))

if __name__ == "__main__":
    main()
