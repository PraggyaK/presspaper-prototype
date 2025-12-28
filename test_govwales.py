import requests
from bs4 import BeautifulSoup

url = "https://www.gov.wales/announcements?page=0"
r = requests.get(url, headers={"User-Agent": "PressPaper/1.0"})

print("STATUS:", r.status_code)
print("LENGTH:", len(r.text))

soup = BeautifulSoup(r.text, "html.parser")
links = soup.find_all("a")

print("TOTAL <a> TAGS:", len(links))
for a in links[:20]:
    print("-", a.get_text(strip=True))