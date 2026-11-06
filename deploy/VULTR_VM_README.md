# Vultr VM deployment (one page)

## 1. Create the VM

- Vultr dashboard → Deploy → Cloud Compute.
- OS: Ubuntu 22.04 or 24.04. Smallest size that fits 1 shared CPU / 512 MB or more.
- Deploy, wait for it to show Running, note its public IP.

## 2. SSH in

```bash
ssh root@<VM-IP>
```

## 3. Clone the repo

```bash
git clone <REPO URL> vultr-creator-research
cd vultr-creator-research
```

## 4. Run the deploy script

```bash
bash deploy/vultr-vm-deploy.sh
```

It installs Docker, builds the image, starts the container on port 8080,
opens the firewall, and smoke-checks `/health`.

## 5. Verify

```bash
curl http://localhost:8080/health
```

Then open `http://<VM-IP>:8080/research` in a browser and run one
creator-research workflow end to end.

## 6. Fill in the demo URL

Put `http://<VM-IP>:8080` into `README.md` as the Vultr demo URL
(replacing the `<VULTR DEMO URL — fill after VM deploy>` placeholder).
Optional: put Caddy in front for HTTPS (see the script's next-steps output).

## Updating

```bash
cd vultr-creator-research && git pull && bash deploy/vultr-vm-deploy.sh
```
