import urllib.request
import json

def get(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def post(url, data):
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

# 1. Root
root = get('http://127.0.0.1:8765/')
print(f"Root: {root.get('name')} (Status: {root.get('status')})")

# 2. Catalog
catalog = get('http://127.0.0.1:8765/api/learning/catalog')
exercises = catalog.get('exercises', [])
print(f"Catalog: {len(exercises)} exercises loaded")
for ex in exercises:
    print(f"  [{ex['exercise_id']}] {ex['display_name']} ({ex['difficulty']}, {ex['skill_practiced']})")

# 3. Starter recommendations
starter = post('http://127.0.0.1:8765/api/learning/recommend', {})
is_starter = starter.get('is_starter_path')
recs = starter.get('recommended_exercises', [])
print(f"\nStarter path (is_starter={is_starter}): {len(recs)} recommended")
for r in recs:
    print(f"  #{r.get('priority')} {r.get('display_name')} -> {r.get('target_activity_url')} ({r.get('priority_label')})")

# 4. Deficit recommendations (Story missed facts + low score)
deficit = post('http://127.0.0.1:8765/api/learning/recommend', {
    'current_session': {
        'story': {'completed': True, 'score_percent': 40.0, 'missed_facts': ['name', 'location']}
    }
})
recs_deficit = deficit.get('recommended_exercises', [])
print(f"\nDeficit path (is_starter={deficit.get('is_starter_path')}): {len(recs_deficit)} recommended")
for r in recs_deficit:
    print(f"  #{r.get('priority')} {r.get('display_name')} (Trigger: {r.get('supporting_metric')})")

# 5. Practice progress tracking
prog = post('http://127.0.0.1:8765/api/learning/progress', {
    'practice_records': [
        {'exercise_id': 'ex_narrative_retell_foundations', 'score': 90.0, 'duration_seconds': 300, 'timestamp': '2026-11-14T00:00:00Z'},
        {'exercise_id': 'ex_dual_feature_binding', 'score': 95.0, 'duration_seconds': 240, 'timestamp': '2026-11-14T00:05:00Z'}
    ]
})
print(f"\nProgress total completed: {prog.get('total_activities_completed')}")
print(f"Unique exercises: {prog.get('unique_exercises_count')}")
consistency = prog.get('consistency', {})
print(f"Active practice days: {consistency.get('days_active_count')}")
print(f"Consistency label: {consistency.get('consistency_label')}")
print(f"Scientific notice: {prog.get('scientific_notice')[:60]}...")
print("\nALL API ENDPOINTS VERIFIED SUCCESSFULLY!")
