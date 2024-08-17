import requests

def search_missing_persons(search_params):
    # API endpoint for NamUs Missing Persons Search
    url = 'https://www.namus.gov/api/CaseSets/NamUs/MissingPersons/Search'

    # Headers for the request
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json;charset=UTF-8',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Referer': 'https://www.namus.gov/MissingPersons/Search',
        'Origin': 'https://www.namus.gov'
    }

    # Convert search parameters to JSON payload
    json_payload = search_params

    # Perform the POST request
    response = requests.post(url, headers=headers, json=json_payload)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse and return the JSON response
        return response.json()
    else:
        # Handle error
        response.raise_for_status()

def process_missing_persons_data(data):
    # Extract cases from the response
    cases = data.get('cases', [])

    case_info_list = []
    for case in cases:
        case_info_list.append({
            'Case Number': case.get('caseNumber', 'N/A'),
            'Name': case.get('name', 'N/A'),
            'Date of Birth': case.get('dateOfBirth', 'N/A'),
            'Age': case.get('age', 'N/A'),
            'Location': f"{case.get('location', {}).get('city', 'N/A')}, {case.get('location', {}).get('state', 'N/A')}",
            'Details': case.get('details', 'No details available')
        })

    return case_info_list

# Example usage
search_params = {
    "caseStatus": "Missing",
    "caseType": "Open",
    "ageRange": {"min": 18, "max": 65},
    "location": {"state": "California"},
    "dateRange": {"start": "2020-01-01", "end": "2024-12-31"}
}

results = search_missing_persons(search_params)
processed_results = process_missing_persons_data(results)

# Print results
for case in processed_results:
    print(f"Case Number: {case['Case Number']}")
    print(f"Name: {case['Name']}")
    print(f"Date of Birth: {case['Date of Birth']}")
    print(f"Age: {case['Age']}")
    print(f"Location: {case['Location']}")
    print(f"Details: {case['Details']}\n")
