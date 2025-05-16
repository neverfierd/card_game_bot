import sqlite3
from sys import stdin


def get_magic_services(genie_name, db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM Genies WHERE genie = ?", (genie_name,))
    genie_id = cursor.fetchone()
    if not genie_id:
        return []
    genie_id = genie_id[0]
    cursor.execute("SELECT place FROM Places WHERE genie_id = ?", (genie_id,))
    places = cursor.fetchall()
    if not places:
        return []
    max_place_length = max(len(place[0]) for place in places)
    cursor.execute("""
        SELECT DISTINCT magic 
        FROM Magics 
        WHERE genie_id = ? AND hair <= ?
        ORDER BY magic DESC
    """, (genie_id, max_place_length))
    services = [row[0] for row in cursor.fetchall()]
    conn.close()
    return services


if __name__ == "__main__":
    genie_name = stdin.readline().strip()
    db_file = stdin.readline().strip()
    services = get_magic_services(genie_name, db_file)
    for service in services:
        print(service)
