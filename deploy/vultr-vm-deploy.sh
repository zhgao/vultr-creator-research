#!/usr/bin/env bash
# Deploy vultr-creator-research on a fresh Vultr Cloud Compute VM.
# Run as root on the VM after cloning the repo:
#   git clone <REPO URL> vultr-creator-research
#   cd vultr-creator-research
#   sudo bash deploy/vultr-vm-deploy.sh
# Requires: Ubuntu 22.04 or 24.04, Docker installed by this script.
# Cost note: this runs on the Vultr VM itself; no other spend is needed.
set -euo pipefail

echo "== Installing Docker =="
apt-get update -y
apt-get install -y docker.io curl ufw

echo "== Building image =="
docker build -t creator-research .

echo "== Starting container =="
docker rm -f creator-research 2>/dev/null || true
docker run -d --name creator-research --restart unless-stopped -p 8080:8080 creator-research

echo "== Opening firewall =="
ufw allow 8080/tcp || true
ufw --force enable || true

echo "== Smoke check =="
sleep 5
curl -fsS http://localhost:8080/health

echo ""
echo "== Done =="
VM_IP="$(hostname -I | awk '{print $1}')"
echo "Public URL: http://${VM_IP}:8080"
echo "Check the brief page at: http://${VM_IP}:8080/research"
echo "Next steps:"
echo "  1. Open http://${VM_IP}:8080/health in a browser — it should return OK."
echo "  2. Fill the public URL into README.md as the Vultr demo URL."
echo "  3. Optional HTTPS: install Caddy and reverse-proxy :8080 (caddy reverse-proxy --from <your-domain> --to localhost:8080)."
echo "  4. To update: git pull, then re-run this script."
