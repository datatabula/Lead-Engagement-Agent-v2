import re

COMPANY_LEGAL_SUFFIXES = [
    "corporation", "incorporated", "limited", "company",
    "co ltd", "ltd", "co", "corp", "inc", "kk", "gk", "llc", "plc", "gmbh", "sa"
]

def normalize_company_name(name):
    normalized = name.lower()
    #re.sub() means replace matching text
    #replaces every period and comma and to implement it on normalized and save it to normalized
    normalized = re.sub(r"[.,]", "",normalized)
    # split it into words to prepare it for word matching
    words = normalized.split()        #["dena", "co", "ltd"]

    # chops off the legal ending logic. 
    # loops over the name until it doesn't recognize any more suffixes
    # changed staying False is what ends the loop. First, set it to true so the while loop can run the first time.
    changed = True          #changed in the true condition gives the loop permission to run for the firs ttime
    while changed and words :   #for as long as changed is true and words is not empty, then continue the loop. It was true, so enter the loop.
        changed = False         #reset it for this new round. assume nothing will be removed during this new check
        for suffix in COMPANY_LEGAL_SUFFIXES:
                suffix_words = suffix.split()               # makes the split version of each element in company_legal_suffixes and stores it in suffix_words  "co ltd" -> (["co", "ltd"]). 
                if words[-len(suffix_words):] == suffix_words:  
                                                                #[-2:] means the last two words    
                                                                #If the words at the end of the company name equal the suffix, remove those words from the company name.
                    words = words[:-len(suffix_words)]          #[:-2] means everything except the last two words 
                                                                # this rebuilds words with the matched suffix chopped off the end. In our example: ["dena", "co", "ltd"][:-2] gives ["dena"].
                                                                # think of : as "starting from"
                    changed = True
                    break
    # Glues whatever words are left back together into one string, and returns it.
    return " ".join(words).strip()





clients_of_competitor = {
    "Berlitz Japan": ["Mitsubishi Gas Chemical", "Nomura Research Institute", "Shiseido", "Toyota Auto Body", "LIXIL", "Taisei Corporation", "Kawasaki Heavy Industries", "Melco Holdings", "Philip Morris Japan", "JTB", "Toyota Motor Corporation", "WestRock"],
    "Bizmates": ["Mitsubishi Estate Residence", "Fujitsu", "TikTok for Business", "THK", "Shimadzu Corporation", "Nomura Trading"],
    "PROGRIT": ["Eureka", "CADDi", "LIXIL", "Aisin", "Panasonic Electric Works", "Hitachi", "Panasonic Energy", "ABeam Consulting", "SOMPO Holdings", "Asahi Group Holdings"],
    "Gaba": ["Konica Minolta", "Ezaki Glico", "ITO EN", "S.T. Corporation", "CyberAgent", "Dell Technologies Japan", "Canon IT Solutions", "eBay Japan", "Sumitomo Life Insurance", "Zeria Pharmaceutical", "Lawson", "FamilyMart", "Japan Airlines", "Toei Animation"],
    "EF Corporate Learning": ["Nike", "Amazon", "H&M", "Bayer", "Philips", "Capgemini", "Fujitsu", "Panasonic Connect", "ArcelorMittal", "Sandvik", "Randstad", "Coca-Cola FEMSA", "Diversey", "Toyota", "Unilever"],
    "Linguage": ["Toyota Motor Corporation", "Hitachi Institute of Management Development", "Prince Hotels", "Nissan Motor", "Mitsui Fudosan", "Nippon Piston Ring", "JX Nippon Mining & Metals", "Sanyo Shokai", "JFE Life"],
    "ALC": ["ANA", "UBE", "Fujitsu Learning Media", "Mitsui O.S.K. Lines", "Nissan Chemical", "JGC Holdings", "Mitsui Fudosan", "LOFT"],
    "Native Camp": ["Osaka Gas", "Japan Display", "Money Forward", "Ise-Shima Resort Management", "Tobii Technology", "Houlihan Lokey", "Fujitsu", "Bristol Myers Squibb", "Sumitomo Mitsui Construction", "Yanmar Construction Equipment", "Nippon Steel Engineering", "Japan Post", "Hewlett Packard Japan", "JR East"],
    "QQEnglish": ["Lion Corporation", "KDDI Cable Ship", "Nagatanien Holdings", "Green Tec", "Mabuchi Motor", "HENNGE", "HARIO Lampwork Factory", "KISUMA", "Qualicaps", "TVE", "Plumsa", "Flowric", "Kyowa Shipping", "iXgene", "Hibino", "DOCOMO CS"],
    "ECC": ["Toyota Motor Corporation", "Daihatsu Motor", "NTN", "Bosch Japan", "Sumitomo Electric Industries", "Hosiden", "ITP", "Miyazaki Seiko", "Mikasa Shoji", "Toyo Tanso"],
    "DMM Eikaiwa": ["CSL Behring", "Wakutory", "Wake Town"],
    "HanasoBiz": ["Kubota Education Center", "Sanyo Chemical Industries", "TESEC"]
}

# cross-checks the target company for its existence in the clients of competitor list
def find_competitors_client_evidence(company):
    normalized_target = normalize_company_name(company)

    for competitor, clients in clients_of_competitor.items():
        for client in clients:
            if normalize_company_name(client) == normalized_target:
                return competitor
    return None


import csv
from models import DistantConnection, ContactDetails

DISTANT_CONNECTIONS_FILE = "distant_connection.csv"

def find_distant_connections(lead_name, company):
    matches = []

     # open the CSV file and read it as a list of dictionaries, one per row,
    # using the header row as each dictionary's keys
    with open(DISTANT_CONNECTIONS_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # go through the CSV one row (one known connection) at a time
        for row in reader:
            full_name_jp = row["Last Name_jp"] + row["First Name_jp"]
            full_name_en = f"{row['First Name']} {row['Last Name']}".strip()
            # build this row's name both ways — kanji (family name first, no space)
            # and romaji (given name first, with a space) — since we don't know
            # which form the incoming lead_name will be in
            
            # there'S a match if a lead_name was actually given AND it matches this row's name,
            # in either the kanji form or the romaji form (case/whitespace-insensitive)
            name_match = lead_name is not None and (
                lead_name == full_name_jp
                or lead_name.strip().lower() == full_name_en.strip().lower()
            )

            # true if the target company matches this row's company, once both sides
            # have their legal suffixes stripped off for a fairer comparison
            company_match = normalize_company_name(company) == normalize_company_name(row["Company"])

            # a row counts as a match if it hit on name, company, or both
            if name_match or company_match:
                # build the actual contact info for this matched row —
                # prefer the kanji name if we have one, otherwise fall back to romaji
                contact = ContactDetails(
                    name=full_name_jp if row["First Name_jp"] else full_name_en,
                    name_romanized=full_name_en,
                    role_title=row["Position"],
                    email=row["Email Address"] or None,
                    linkedin_url=row["URL"],
                    source_url=row["URL"]
                )
                # pair that contact with who at COMAS actually knows them, and save it
                matches.append(DistantConnection(
                    whose_connection=row["whose_connection"],
                    contact=contact
                ))
     # hand back every match found — empty list if nothing matched at all
    return matches

from models import PreResearchContext
from cache import get_cached_research

def build_preresearch_context(lead_name, company):
    # true only when no lead name was given at all — triggers the HR/L&D fallback treatment
    needs_hr_fallback = lead_name is None

    # reuse the existing cache-check function — returns real findings on a hit, None on a miss
    has_cached_research = get_cached_research(company, lead_name)

    # look up any known distant connections by name (kanji or romaji) or by company
    has_distant_cxn = find_distant_connections(lead_name, company)

    # cross checks company name on competitor's client list
    competitor_it_was_found_under = find_competitors_client_evidence(company)

   
    return PreResearchContext(
        needs_hr_fallback=needs_hr_fallback,
        has_cached_research=has_cached_research,
        has_distant_cxn=has_distant_cxn,
        competitor_it_was_found_under= competitor_it_was_found_under
    )


# quick manual test — running this file directly builds a full PreResearchContext
# for a real lead/company and prints it, so we can eyeball that everything
# (cache check + distant-connection lookup) is working together correctly

if __name__ == "__main__":
    print(build_preresearch_context("Masayuki Igarashi", "Toyota Motor Corporation"))