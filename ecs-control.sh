#!/bin/bash
# ECS Service Control Script
# Stop/Start the voice-bot-mvp service to save costs

set -e

CLUSTER="voice-bot-mvp-cluster"
SERVICE="voice-bot-mvp-svc"
REGION="ap-south-1"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

get_service_status() {
    local response=$(aws ecs describe-services \
        --cluster $CLUSTER \
        --services $SERVICE \
        --region $REGION \
        --query 'services[0].[runningCount,desiredCount]' \
        --output json)

    local running=$(echo $response | python -c "import sys, json; print(json.load(sys.stdin)[0])")
    local desired=$(echo $response | python -c "import sys, json; print(json.load(sys.stdin)[1])")

    echo "Running: $running, Desired: $desired"
}

stop_service() {
    print_status "Stopping ECS service..."

    aws ecs update-service \
        --cluster $CLUSTER \
        --service $SERVICE \
        --desired-count 0 \
        --region $REGION \
        --output json > /dev/null

    print_status "Service scaled to 0 tasks. Service is now stopped."
    print_status "Cost is now: $0/hour"
}

start_service() {
    print_status "Starting ECS service..."

    aws ecs update-service \
        --cluster $CLUSTER \
        --service $SERVICE \
        --desired-count 1 \
        --region $REGION \
        --output json > /dev/null

    print_status "Service scaled to 1 task. Service is starting..."
    print_status "This will take ~30-60 seconds to fully start"
}

status_service() {
    print_status "Current service status:"
    echo "Cluster: $CLUSTER"
    echo "Service: $SERVICE"
    echo "Status: $(get_service_status)"
}

# Main logic
case "${1:-status}" in
    stop)
        stop_service
        ;;
    start)
        start_service
        ;;
    status)
        status_service
        ;;
    toggle)
        status=$(get_service_status)
        if [[ $status == *"Running: 0"* ]]; then
            print_status "Service is stopped. Starting it..."
            start_service
        else
            print_status "Service is running. Stopping it..."
            stop_service
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|status|toggle}"
        echo ""
        echo "Examples:"
        echo "  $0 stop    # Stop the service (save costs)"
        echo "  $0 start   # Start the service"
        echo "  $0 status  # Check current status"
        echo "  $0 toggle  # Toggle between start/stop"
        exit 1
        ;;
esac
