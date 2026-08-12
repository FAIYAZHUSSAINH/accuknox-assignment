rows = """name,email
Aarthi Raman,aarthi.raman@example.com
Bharath Kumar,BHARATH.KUMAR@EXAMPLE.COM
Chitra Devi,  chitra.devi@example.com  
José Fernandes,jose.fernandes@example.com
Elango S,elango.example.com
Fathima Begum,
,ganesh.iyer@example.com
Harini R,harini.r@example.com
Aarthi Raman,aarthi.raman@example.com
Janani P,janani.p@example.com,9876543210
Karthik M,karthik.m@example.com
"""

# utf-8-sig writes a BOM, which is what Excel does when you "Save as CSV UTF-8".
with open("users.csv", "w", encoding="utf-8-sig", newline="") as f:
    f.write(rows)

print("wrote users.csv")
