import json
import subprocess
from datetime import datetime

# Get HourlyCost metrics from deployment start (Mar 6)
result = subprocess.run([
    'aws', 'cloudwatch', 'get-metric-statistics',
    '--namespace', 'voicebot/operations',
    '--metric-name', 'HourlyCost',
    '--start-time', '2026-03-06T00:00:00Z',
    '--end-time', '2026-03-10T00:00:00Z',
    '--period', '3600',  # 1 hour
    '--statistics', 'Maximum',
    '--region', 'ap-south-1'
], capture_output=True, text=True)

data = json.loads(result.stdout)
datapoints = sorted(data.get('Datapoints', []), key=lambda x: x['Timestamp'])

if datapoints:
    hourly_cost = datapoints[0]['Maximum']
    hours_running = len(datapoints)
    cumulative = hourly_cost * hours_running
    print(f"Hourly Cost: ${hourly_cost:.4f}")
    print(f"Hours Running: {hours_running}")
    print(f"Estimated Total Cost (so far): ${cumulative:.2f}")
    print(f"Period: Mar 6 - Mar 9, 2026")
