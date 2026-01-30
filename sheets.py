import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import os.path
import pickle
import pandas as pd
from typing import List, Dict, Union, Optional, Any

# Scope needed for Google Sheets and Drive API
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

class SheetUploader:
    def __init__(self, spreadsheet_id: str, credentials_path: str = "credentials.json", token_path: str = "token.pickle"):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.client = None
        self.sheet = None

    def authenticate(self):
        """Authenticates using Service Account (preferred) or OAuth."""
        creds = None
        
        # 1. Try Service Account first
        if os.path.exists(self.credentials_path):
            try:
                # distinct check: is it a service account json?
                # simple heuristic: check content, or just try loading
                creds = Credentials.from_service_account_file(self.credentials_path, scopes=SCOPES)
                self.client = gspread.authorize(creds)
                print("Authenticated using Service Account.")
                return
            except ValueError:
                print("Credential file found but failed to load as Service Account. Trying OAuth...")

        # 2. Fallback to OAuth (Client Secrets)
        # This requires user interaction on first run
        if os.path.exists(self.token_path):
            with open(self.token_path, "rb") as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                     raise FileNotFoundError(f"Could not find credentials file at {self.credentials_path}")
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(self.token_path, "wb") as token:
                pickle.dump(creds, token)

        self.client = gspread.authorize(creds)
        print("Authenticated using OAuth.")

    def _get_worksheet(self, tab_name: str):
        if not self.client:
            self.authenticate()
        
        try:
            sh = self.client.open_by_key(self.spreadsheet_id)
        except gspread.SpreadsheetNotFound:
            raise ValueError(f"Spreadsheet with ID {self.spreadsheet_id} not found.")

        try:
            worksheet = sh.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            # Create if not exists
            worksheet = sh.add_worksheet(title=tab_name, rows=1000, cols=20)
            print(f"Created new worksheet: {tab_name}")
        
        return worksheet

    def upload_dataframe(self, tab_name: str, data: List[Dict[str, object]]):
        """
        Uploads a list of dictionaries (rows) to a specific tab.
        Overwrites existing content.
        """
        if not data:
            print(f"No data to upload for {tab_name}.")
            return

        df = pd.DataFrame(data)
        worksheet = self._get_worksheet(tab_name)
        
        # Clear existing content
        worksheet.clear()
        
        # Prepare data for upload
        # header
        header = df.columns.tolist()
        # values
        # Avoid astype(str) to maintain numeric types in Google Sheets
        # Use where(pd.notnull(df), None) to handle NaN for gspread
        values = df.where(pd.notnull(df), "").values.tolist()
        
        # Update
        worksheet.update(range_name='A1', values=[header] + values)
        print(f"Uploaded {len(values)} rows to {tab_name}.")

    def read_sheet(self, tab_name: str) -> List[Dict[str, Any]]:
        """
        Reads all data from a specific tab and returns as a list of dictionaries.
        """
        worksheet = self._get_worksheet(tab_name)
        return worksheet.get_all_records()

    def append_dataframe(self, tab_name: str, data: List[Dict[str, object]]):
        # Implementation for append if needed later
        pass
