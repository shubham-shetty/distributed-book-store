#!/bin/bash
# Deploys and starts the application on a remote cloud VM you already provisioned.
# Works with any provider (AWS EC2, GCP, DigitalOcean, ...) -- bring your own SSH key and host.
#
# Setup:
#   cp deploy.env.example deploy.env
#   # edit deploy.env with your SSH_KEY_PATH / REMOTE_USER / REMOTE_HOST
#   ./deploy.sh          # sync code, install deps, start the services
#   ./deploy.sh --stop   # stop the services on the remote host
#
# Firewall/security-group note: only the front-end port (12345 by default) needs to
# be reachable from outside the VM. The catalog and order-replica ports (50042-50045)
# are only ever dialed via "localhost" by the services themselves, so they can stay
# closed to the outside world.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$SCRIPT_DIR/deploy.env"

if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
fi

: "${SSH_KEY_PATH:?Set SSH_KEY_PATH in deploy.env (copy deploy.env.example first)}"
: "${REMOTE_USER:?Set REMOTE_USER in deploy.env}"
: "${REMOTE_HOST:?Set REMOTE_HOST in deploy.env}"
REMOTE_PORT="${REMOTE_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:-~/distributed-store-src}"

SSH_KEY_PATH="${SSH_KEY_PATH/#\~/$HOME}"
SSH="ssh -i $SSH_KEY_PATH -p $REMOTE_PORT -o StrictHostKeyChecking=accept-new $REMOTE_USER@$REMOTE_HOST"
RSYNC_SSH="ssh -i $SSH_KEY_PATH -p $REMOTE_PORT -o StrictHostKeyChecking=accept-new"

if [ "${1:-}" = "--stop" ]; then
    echo "Stopping remote services on $REMOTE_HOST..."
    $SSH "pkill -f 'catalog/catalog.py' || true; pkill -f 'order/order.py' || true; pkill -f 'front_end/front_end.py' || true"
    echo "Stopped."
    exit 0
fi

echo "Syncing code to $REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR ..."
$SSH "mkdir -p $REMOTE_DIR"
rsync -avz -e "$RSYNC_SSH" \
    --exclude 'venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude 'deploy/deploy.env' \
    "$SRC_DIR/" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/"

echo "Installing dependencies and starting services on $REMOTE_HOST ..."
$SSH "cd $REMOTE_DIR && \
    pip3 install -r requirements.txt && \
    chmod +x build.sh && \
    nohup ./build.sh 0.0.0.0 > deploy.log 2>&1 < /dev/null &"

echo ""
echo "Deployed. Front-end should be reachable at http://$REMOTE_HOST:12345 once services finish starting"
echo "(check remote $REMOTE_DIR/deploy.log if it isn't). Point your client at it with:"
echo "  python3 client/client.py --host $REMOTE_HOST --port 12345 --t <book-title>"
echo ""
echo "Make sure your cloud provider's firewall/security group allows inbound TCP on port 12345 from your IP."
