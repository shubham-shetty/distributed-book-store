# Cloud Deployment

Run the application on any cloud VM you already provisioned (AWS EC2, GCP Compute Engine,
DigitalOcean, a bare VPS, ...). This is provider-agnostic -- bring your own SSH key and host,
nothing here is tied to a specific account or provider.

## Prerequisites

- A running VM with SSH access and Python 3 + pip installed.
- Your SSH private key for that VM, stored locally (never committed to this repo).
- Inbound firewall / security-group rule allowing TCP on the front-end port (12345 by default)
  from wherever your client will connect. The internal service ports (50042 for catalog,
  50043-50045 for the order replicas) never need to be exposed publicly -- the services only ever
  reach each other over `localhost`, so they must all run on the same VM.

## Usage

```shell
cd src/deploy
cp deploy.env.example deploy.env
# edit deploy.env: set SSH_KEY_PATH, REMOTE_USER, REMOTE_HOST (and REMOTE_PORT/REMOTE_DIR if needed)

./deploy.sh        # rsyncs src/ to the VM, installs requirements.txt, and starts all 5 services
./deploy.sh --stop # stops the services on the VM
```

`deploy.env` is gitignored, so your key path and host are never committed -- only
`deploy.env.example` (the template) is tracked.

Once deployed, point a client at it from your local machine:

```shell
python3 client/client.py --host <REMOTE_HOST> --port 12345 --t 1984
```

## Notes

- `deploy.sh` always starts the remote front-end bound to `0.0.0.0` (not the value of
  `REMOTE_HOST`) so it accepts connections from outside the VM.
- Remote service logs land in `<REMOTE_DIR>/deploy.log` on the VM.
- This script is intentionally minimal (rsync + pip install + nohup'd `build.sh`) rather than a
  full provisioning tool -- it assumes the VM itself already exists and is reachable over SSH.
- **Never store your private key inside this repo** (not even gitignored) -- keep it wherever you
  normally keep SSH keys (e.g. `~/.ssh/`) and just point `SSH_KEY_PATH` at it.

## Example: provisioning an AWS EC2 instance

If you don't have a VM yet, here's the shape of it on EC2 (adapt image/instance type/region to
your account -- these are placeholders, not real values):

```shell
# Launch an instance
aws ec2 run-instances \
    --image-id ami-xxxxxxxxxxxxxxxxx \
    --instance-type t3.small \
    --key-name your-keypair-name > instance.json

# Get its public DNS
aws ec2 describe-instances --instance-id <instance-id-from-instance.json>

# Open the ports the app needs: 22 for SSH, 12345 for the front-end
aws ec2 authorize-security-group-ingress --group-name default --protocol tcp --port 22 --cidr <your-ip>/32
aws ec2 authorize-security-group-ingress --group-name default --protocol tcp --port 12345 --cidr 0.0.0.0/0
```

Then set `REMOTE_HOST` in `deploy.env` to the instance's public DNS/IP and run `./deploy.sh`.
`instance.json` from `describe-instances` contains account-identifying details (account ID,
VPC/subnet/security-group IDs) -- keep it out of version control (already covered by
`.gitignore`).
