import sqlite3

def cleanup():
    conn = sqlite3.connect('lead_machine.db')
    cursor = conn.cursor()
    
    # 1. Delete garbage contacts
    cursor.execute("DELETE FROM contacts WHERE name LIKE '%with%' OR name LIKE '%interview%' OR name LIKE '%was%' OR name LIKE '%has%' OR length(name) < 5")
    
    # 2. Delete orphaned leads
    cursor.execute("DELETE FROM leads WHERE id NOT IN (SELECT lead_id FROM contacts)")
    
    # 3. Delete duplicate business names (keep only the first one)
    cursor.execute("""
    DELETE FROM leads 
    WHERE id NOT IN (
        SELECT MIN(id) 
        FROM leads 
        GROUP BY business_name
    )
    """)
    
    conn.commit()
    count = cursor.rowcount
    conn.close()
    print(f"Cleaned up {count} entries.")

if __name__ == "__main__":
    cleanup()
