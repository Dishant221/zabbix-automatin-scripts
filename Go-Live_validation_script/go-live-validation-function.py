from datetime import datetime, timedelta
import logging
import os

BaseDirectory = os.path.dirname(os.path.abspath(__file__))

logfilePATH = os.path.join(BaseDirectory,"DATA","LOG_OUTPUT","GO-LIVE_VALIDATION_LOGS.log")


logging.basicConfig(filename=logfilePATH,
                    filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

def go_live_host(zapi, host_id, hostgroup_id, dry_run=False):
    """
    Perform Go-Live validation and execution
    
    Params:
        zapi        : ZabbixAPI object
        host_id     : Host ID
        hostgroup_id: Host Group ID
        dry_run     : If True, no changes will be made
    
    Returns:
        dict: status + message
    """

    try:
        now = int(datetime.now().timestamp())
        seven_days_ago = now - (7 * 24 * 60 * 60)
        six_hours = 6 * 60 * 60

        print("🔍 Step 1: Fetching problems from last 7 days...")

        # -------------------------------
        # 1. Last 7 days problems (HG)
        # -------------------------------
        problems_7d = zapi.problem.get(
            groupids=[hostgroup_id],
            time_from=seven_days_ago,
            severities=[4, 5],  # High & Disaster
            output=["eventid"]
        )

        high_disaster_count = len(problems_7d)
        print(f"High+Disaster (7d): {high_disaster_count}")

        if high_disaster_count >= 30:
            return {"status": "FAILED", "reason": "High+Disaster problems >= 30 in last 7 days"}

        # -------------------------------
        # 2. Active problems (Host)
        # -------------------------------
        print(" Step 2: Fetching active problems...")

        active_problems = zapi.problem.get(
            hostids=[host_id],
            recent=True,
            output=["eventid", "clock", "name", "r_eventid"]
        )

        active_problems = [p for p in active_problems if p["r_eventid"] == "0"]

        active_count = len(active_problems)
        print(f"Active Problems: {active_count}")

        if active_count >= 5:
            return {"status": "FAILED", "reason": "Active problems >= 5"}

        # -------------------------------
        # 3. Problem age check (optional)
        # -------------------------------
        print(" Step 3: Checking problem age...")

        for p in active_problems:
            age = now - int(p["clock"])
            if age > six_hours:
                return {
                    "status": "FAILED",
                    "reason": f"Problem older than 6h: {p['name']}"
                }

        print("✅ Validation Passed")

        if dry_run:
            return {"status": "DRY_RUN", "message": "Validation passed, no changes executed"}

        # -------------------------------
        # 4. Close active problems
        # -------------------------------
        print("⚙️ Step 4: Closing active problems...")

        for p in active_problems:
            try:
                zapi.event.acknowledge(
                    eventids=[p["eventid"]],
                    action=1,  # Close problem
                    message="Auto-closed during GO-LIVE"
                )
                print(f"Closed problem: {p['eventid']}")
            except Exception as e:
                print(f" Failed to close {p['eventid']}: {e}")

        # -------------------------------
        # 5. Rename Host Group
        # -------------------------------
        print("⚙️ Step 5: Renaming hostgroup...")

        hg = zapi.hostgroup.get(
            groupids=[hostgroup_id],
            output=["name"]
        )

        if not hg:
            return {"status": "FAILED", "reason": "Hostgroup not found"}

        old_name = hg[0]["name"]
        print(f"Old Hostgroup: {old_name}")
        logging.info("host: {hostid} :Old Hostgroup: {old_name}")

        if old_name.startswith("GO-LIVE"):
            return {"status": "SKIPPED", "message": "Already GO-LIVE"}

        parts = old_name.split("/")

        try:
            # Extract parts safely
            portfolio = parts[-4]
            product = parts[-3]
            hub_id = parts[-2]

            new_name = f"GO-LIVE/{portfolio}/{product}/{hub_id}/E2Customer"

        except Exception:
            return {"status": "FAILED", "reason": "Invalid hostgroup naming format"}

        print(f"New Hostgroup: {new_name}")

        try:
            zapi.hostgroup.update(
                groupid=hostgroup_id,
                name=new_name
            )
        except Exception as e:
            return {"status": "FAILED", "reason": f"Hostgroup rename failed: {e}"}

        print("🎉 GO-LIVE SUCCESS")

        return {
            "status": "SUCCESS",
            "message": "Host moved to GO-LIVE successfully",
            "new_hostgroup": new_name
        }

    except Exception as e:
        return {"status": "ERROR", "reason": str(e)}
    
