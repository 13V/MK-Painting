"""
Helper script to fetch your Google Business Profile (GBP) Account ID and Location ID.

Run this script once to print out your IDs, then add them to your .env file:
GBP_ACCOUNT_ID="your_account_id"
GBP_LOCATION_ID="your_location_id"
"""

import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

def fetch_gbp_ids():
    creds_json = os.environ.get("GSC_CREDENTIALS_JSON")
    if not creds_json:
        creds_path = os.environ.get("GSC_CREDENTIALS_PATH", "credentials.json")
        if not os.path.exists(creds_path):
            print("❌ Cannot find credentials.json. Make sure your Google Cloud credentials are set.")
            return
            
        with open(creds_path, "r", encoding="utf-8") as f:
            creds_json = f.read()

    creds_info = json.loads(creds_json)
    
    try:
        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/business.manage"],
        )
        
        # Build the Account Management API client
        account_service = build('mybusinessaccountmanagement', 'v1', credentials=credentials)
        
        print("🔍 Fetching Google Business Profile Accounts...")
        accounts_response = account_service.accounts().list().execute()
        accounts = accounts_response.get("accounts", [])
        
        if not accounts:
            print("❌ No GBP accounts found for this service account.")
            print("Make sure this service account email is added as a 'Manager' to your Google Business Profile.")
            return
            
        for account in accounts:
            account_name = account.get("name") # e.g., "accounts/12345"
            account_id = account_name.split("/")[-1]
            print(f"\n✅ Found Account: {account.get('accountName')} (ID: {account_id})")
            
            # Fetch locations for this account
            # Requires the mybusinessbusinessinformation API
            info_service = build('mybusinessbusinessinformation', 'v1', credentials=credentials)
            locations_response = info_service.accounts().locations().list(parent=account_name).execute()
            locations = locations_response.get("locations", [])
            
            if not locations:
                print("   ⚠ No locations/businesses found under this account.")
                continue
                
            for loc in locations:
                loc_id = loc.get("name").split("/")[-1]
                print(f"   📍 Location: {loc.get('title')} (ID: {loc_id})")
                
                print("\n--- Add these to your .env file ---")
                print(f'GBP_ACCOUNT_ID="{account_id}"')
                print(f'GBP_LOCATION_ID="{loc_id}"')
                print("-----------------------------------")
                
    except Exception as e:
        print("\n❌ API Error:", e)
        print("\nEnsure you have enabled the following APIs in your Google Cloud Console:")
        print("1. Google My Business Account Management API")
        print("2. Google My Business Business Information API")

if __name__ == "__main__":
    fetch_gbp_ids()
