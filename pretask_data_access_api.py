
# pretask_data_access_api.py
"""
REST API helper for the UI automation project's pretask data access step.

WHY THIS FILE EXISTS:
    In the UI automation project, the role-assignment step is still done through
    the browser UI because that is already built and working well enough.

    The weak part of the pretask is the "Manage Data Access for Users" UI flow,
    which is flaky because Oracle autocomplete and row handling can be unstable.

    This file replaces ONLY the data access portion with REST API calls.

WHAT THIS FILE DOES:
    - Connects directly to the Fusion REST API
    - Reads credentials/base URL from environment variables
    - Builds the 2 fixed data access rows needed for the pretask
    - Posts data access rows
    - Skips duplicate rows when Oracle says they already exist
    - Supports dry_run for safe testing

INTENDED FLOW:
    1) UI automation logs in and adds roles in Security Console
    2) UI automation calls this helper
    3) This helper grants the 2 fixed Business Unit data access rows
    4) UI automation continues

IMPORTANT NOTE:
    The target user should already have the relevant roles before this file is run.
    Otherwise Oracle may reject the data access POST with a message such as:
        "The value of the attribute Role isn't valid."
    Ui Automation gives the roles beforehand.

CONFIRMED ROLE CODES:
    1) Procurement Catalog Administrator
       -> ORA_POR_PROCUREMENT_CATALOG_ADMINISTRATOR_ABSTRACT

    2) (client)-BPR IRC Recruiting Setup and Maintenance_JOB
       -> (client)-BPR_IRC_RECRUITING_SETUP_AND_MAINTENANCE_JOB
These are needed for the RESTAPI to work.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()


class PretaskDataAccessApiClient:
    """
    Small REST client for the UI automation project's fixed data access pretask.

    AUTHENTICATION:
        Supports either of these environment naming styles:

        Style A:
            TENANT_BASE_URL
            FUSION_USERNAME
            FUSION_PASSWORD

        Style B (current UI automation project):
            TENANT_BASE_URL
            UI_USER
            UI_PASS

    ENDPOINT USED:
        /fscmRestApi/resources/11.13.18.05/dataSecurities

    WHY THIS CLASS EXISTS:
        Keeps all REST behavior in one place so Ui_Automation.py stays focused on UI.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 60,
    ) -> None:
        self.base_url = (base_url or os.getenv("TENANT_BASE_URL") or "").rstrip("/")

        # Support both Fusion-style names and UI automation project names
        self.username = (
            username
            or os.getenv("FUSION_USERNAME")
            or os.getenv("UI_USER")
            or ""
        )

        self.password = (
            password
            or os.getenv("FUSION_PASSWORD")
            or os.getenv("UI_PASS")
            or ""
        )

        self.timeout = timeout

        if not self.base_url:
            raise ValueError("Missing TENANT_BASE_URL in environment/.env")
        if not self.username:
            raise ValueError("Missing FUSION_USERNAME or UI_USER in environment/.env")
        if not self.password:
            raise ValueError("Missing FUSION_PASSWORD or UI_PASS in environment/.env")

        self.endpoint = f"{self.base_url}/fscmRestApi/resources/11.13.18.05/dataSecurities"

        self.session = requests.Session()
        self.session.auth = (self.username, self.password)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    # ---------------------------------------------------------
    # Step 1 - Build fixed records
    # ---------------------------------------------------------

    def build_fixed_records(
        self,
        target_username: str,
        active_flag: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Build the 2 fixed data access rows for the post-refresh pretask.

        RECORDS CREATED:
            1) Procurement Catalog Administrator / Business unit / (client) BU
            2) (client)-BPR IRC Recruiting Setup and Maintenance_JOB / Business unit / (client) BU

        IMPORTANT:
            These use the confirmed internal Oracle role codes directly,
            so no role-map lookup is needed.
        """
        return [
            {
                "SecurityContext": "Business unit",
                "SecurityContextValue": "(client) BU",
                "UserName": target_username,
                "RoleCommonName": "ORA_POR_PROCUREMENT_CATALOG_ADMINISTRATOR_ABSTRACT",
                "ActiveFlag": active_flag,
            },
            {
                "SecurityContext": "Business unit",
                "SecurityContextValue": "(client) BU",
                "UserName": target_username,
                "RoleCommonName": "(client)-BPR_IRC_RECRUITING_SETUP_AND_MAINTENANCE_JOB",
                "ActiveFlag": active_flag,
            },
        ]

    # ---------------------------------------------------------
    # Step 2 - POST one data access row
    # ---------------------------------------------------------

    def post_data_access(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST one data access row to Oracle.

        DUPLICATE HANDLING:
            If Oracle indicates the row already exists, return status='skipped'
            instead of hard-failing.
        """
        payload = {
            "SecurityContext": record["SecurityContext"],
            "SecurityContextValue": record["SecurityContextValue"],
            "UserName": record["UserName"],
            "RoleCommonName": record["RoleCommonName"],
            "ActiveFlag": record["ActiveFlag"],
        }

        response = self.session.post(self.endpoint, json=payload, timeout=self.timeout)

        if response.ok:
            print(
                f"[Data Access API] POSTED: {payload['UserName']} / "
                f"{payload['RoleCommonName']} / {payload['SecurityContextValue']}"
            )
            return {
                "status": "posted",
                "record": payload,
                "response": response.json() if response.text else {},
            }

        body_text = response.text or ""

        duplicate_signals = [
            "already exists",
            "duplicate",
            "The combination already exists",
            "A record with this combination of values already exists",
        ]

        if any(sig.lower() in body_text.lower() for sig in duplicate_signals):
            print(
                f"[Data Access API] SKIPPED duplicate: {payload['UserName']} / "
                f"{payload['RoleCommonName']} / {payload['SecurityContextValue']}"
            )
            return {
                "status": "skipped",
                "record": payload,
                "error": body_text,
            }

        print(
            f"[Data Access API] FAILED: {payload['UserName']} / "
            f"{payload['RoleCommonName']} / {payload['SecurityContextValue']}"
        )
        return {
            "status": "failed",
            "record": payload,
            "error": f"{response.status_code} {body_text}",
        }

    # ---------------------------------------------------------
    # Step 3 - Run full fixed-record flow
    # ---------------------------------------------------------

    def run_fixed_data_access(
        self,
        target_username: str,
        dry_run: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Main entry point for the fixed 2-row pretask flow.

        FLOW:
            1) Build the 2 fixed records
            2) POST each row (or print in dry run)
            3) Return result list
        """
        print(f"\n{'='*60}")
        print("PRETASK DATA ACCESS API")
        print(f"{'='*60}")
        print(f"Target User: {target_username}")
        print(f"Dry Run    : {dry_run}")

        records = self.build_fixed_records(
            target_username=target_username,
            active_flag=True,
        )

        results: List[Dict[str, Any]] = []
        for record in records:
            if dry_run:
                print(f"[Data Access API][DRY RUN] Would POST: {record}")
                results.append({"status": "dry_run", "record": record})
            else:
                results.append(self.post_data_access(record))

        posted = sum(1 for r in results if r["status"] == "posted")
        skipped = sum(1 for r in results if r["status"] == "skipped")
        failed = sum(1 for r in results if r["status"] == "failed")
        dry = sum(1 for r in results if r["status"] == "dry_run")

        print(f"\n[Data Access API] Summary -> Posted={posted} Skipped={skipped} Failed={failed} DryRun={dry}")
        return results


# ---------------------------------------------------------
# Convenience wrapper function for Ui_Automation.py
# ---------------------------------------------------------

def run_fixed_procurement_data_access(
    target_username: str,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """
    Simple wrapper so Ui_Automation.py can call one function.
    """
    client = PretaskDataAccessApiClient()
    return client.run_fixed_data_access(
        target_username=target_username,
        dry_run=dry_run,
    )


# ---------------------------------------------------------
# Optional standalone test
# ---------------------------------------------------------

if __name__ == "__main__":
    """
    Standalone test mode.

    RECOMMENDED FIRST:
        Use dry_run=True for a safe preview.
        Then switch to dry_run=False when ready.
    """
    TEST_USERNAME = "."

    results = run_fixed_procurement_data_access(
        target_username=TEST_USERNAME,
        dry_run=False,
    )

    print("\nReturned Results:")
    for row in results:
        print(row)