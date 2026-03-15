import json
import subprocess

result = subprocess.run([
    'aws', 'cloudwatch', 'get-metric-statistics',
    '--namespace', 'voicebot/operations',
    '--metric-name', 'MonthlyCost',
    '--start-time', '2026-03-01T00:00:00Z',
    '--end-time', '2026-03-10T00:00:00Z',
    '--period', '86400',
    '--statistics', 'Maximum',
    '--region', 'ap-south-1'
], capture_output=True, text=True)

data = json.loads(result.stdout)
if data['Datapoints']:
    latest = sorted(data['Datapoints'], key=lambda x: x['Timestamp'])[-1]
    print(f"Latest Monthly Cost: ${latest['Maximum']:.2f}")
