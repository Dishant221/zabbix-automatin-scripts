#!/usr/bin/env python3
import pymysql
import pymysql.cursors
import json
from typing import List, Dict, Any

QUERY = '''
SELECT
    h.hostid,
    h.name,
    h.status,
    GROUP_CONCAT(DISTINCT g.name ORDER BY g.name SEPARATOR ', ') AS groups_list
FROM hosts h
LEFT JOIN hosts_groups hg ON hg.hostid = h.hostid
LEFT JOIN hstgrp g       ON g.groupid = hg.groupid
WHERE h.status = 0
AND NOT EXISTS (
    SELECT 1
    FROM hosts_groups hg2
    JOIN hstgrp g2 ON g2.groupid = hg2.groupid
    WHERE hg2.hostid = h.hostid
      AND UPPER(g2.name) LIKE 'GO-LIVE%'
)
GROUP BY h.hostid, h.name, h.status
ORDER BY h.name ASC
LIMIT 10;
'''


def rows_to_json(rows):
    """
    Convert a list of row-dicts (as returned by DictCursor.fetchall())
    into a JSON string. Ensures groups_list is a list (possibly empty).
    """
    out: List[Dict[str, Any]] = []

    for row in rows:
        r = dict(row)  # copy so we don't mutate the original cursor row

        gl = r.get("groups_list")
        if gl and isinstance(gl, str):
            # split by comma, strip and filter empties
            r["groups_list"] = [g.strip() for g in gl.split(",") if g.strip()]
        else:
            # ensure always a list
            r["groups_list"] = []

        out.append(r)

    return json.dumps(out, indent=4)


def get_enabled_hostids(connection: pymysql.connections.Connection) -> str:
    """
    Execute the query and return JSON string (rows -> JSON).
    """
    cursor = None
    try:
        # Use DictCursor so fetchall() returns list of dicts
        cursor = connection.cursor()
        cursor.execute(QUERY)
        rows = cursor.fetchall()  # list of dicts
        print(rows)
        return rows_to_json(rows)
    finally:
        if cursor:
            cursor.close()


def make_connection():
    """
    Create and return a pymysql connection configured to use unix socket.
    Update credentials or use env vars/secret manager in real usage.
    """
    return pymysql.connect(
        user="zabbix",
        password="REDACTED",
        database="zabbix",
        port=7009,
        unix_socket="/u01/mysql/7009/var/lib/mysql/mysql_7009.sock",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


if __name__ == "__main__":
    conn = None
    try:
        conn = make_connection()
        json_output = get_enabled_hostids(conn)
        print(json_output)

       
    except Exception as e:
        print("Database Connection Error:", str(e))

    finally:
        if conn:
            conn.close()
