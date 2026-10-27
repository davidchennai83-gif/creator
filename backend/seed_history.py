import sqlite3
import json
from pathlib import Path

conn = sqlite3.connect(Path(__file__).with_name('creator_platform.db'))
cursor = conn.cursor()

events = [
    ('1947-08-15', 'India Independence', 'India gains independence from British rule',
     'இண்டiya independence', 'Indentiya brit rule Tamil 1947',
      ['National sovereignty achieved', 'End of colonial rule', 'First Prime Minister Nehru', 'Tryst with destiny speech', 'National flag hoisting', 'Holiday declared - Independence Day', 'Cultural programs nationwide', 'Tribute to freedom fighters', 'Fireworks and celebrations', 'Patriotic speeches']),

    ('1956-01-01', 'Tamil Official Language', 'Tamil recognized as official language of Tamil Nadu',
     'தமிழ் OFFICIAL', 'Tamil Moliya ariviyal',
      ['Tamil classical language status', 'Official state language', 'Linguistic pride', 'Anti-imposition protests', 'Tamil literature revival', 'Educational medium', 'Cultural identity', 'International recognition', 'Tamil diaspora connection', 'Annual Tamil Language Day']),

    ('1930-02-28', 'Raman Effect Discovery', 'C.V. Raman discovers Raman effect',
     'ராமன் Effects', 'Ci.V.Raman discovery',
      ['Nobel Prize in Physics 1930', 'Indian scientific breakthrough', 'Raman effect phenomenon', 'Light scattering theory', 'National pride for India', 'Raman Research Institute established', 'Inspires young scientists', 'Textbook physics topic', 'Ramanujan connection', 'Annual National Science Day']),

    ('1857-05-10', 'First War of Independence', 'Sepoy Mutiny begins - first war of Indian independence',
     'பrium FIRST', 'Prium first rebellion',
      ['First large-scale rebellion', 'East India Company rule challenged', 'Unified Indian soldiers', 'Brutal suppression', 'Birth of nationalism', 'Led to 1858 Government takeover', 'Heroes remembered today', 'Lessons for freedom struggle', 'Regional variations', 'Historical turning point']),

    ('1917-12-28', 'Women Voting Rights', 'Women granted voting rights in India',
     'பெண்கள் RIGHTS', 'Penkal Val权',
      ['Democratic rights expansion', 'Social reform milestone', 'Suffrage movement', 'Women political participation', 'Global wave of change', 'Tamil Nadu leadership', 'Education empowerment', 'Future legislation paved way', 'International context', 'Ongoing equality journey']),
]

for date, eng_title, eng_desc, tamil_title, tamil_desc, points in events:
    points_json = json.dumps(points)
    cursor.execute('''
        INSERT OR IGNORE INTO history_events (date, event_title, event_description, tamil_title, tamil_description, importance_points)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (date, eng_title, eng_desc, tamil_title, tamil_desc, points_json))

conn.commit()
cursor.execute('SELECT count(*) FROM history_events')
count = cursor.fetchone()[0]
print(f'Inserted {count} history events')

cursor.execute('SELECT event_title, tamil_title, importance_points FROM history_events LIMIT 1')
row = cursor.fetchone()
points_data = json.loads(row[2]) if row[2] else []
points_len = len(points_data)
print(f'Sample: {row[0]}, Tamil: {row[1]}, Points: {points_len} items')
conn.close()
print('Done!')