# Deployment auf Raspberry Pi OS

Getestet mit Raspberry Pi OS (Bookworm, 64-bit). Die App läuft als
systemd-Dienst hinter Caddy (automatisches HTTPS). Empfohlen wird der Zugriff
ausschließlich über **Tailscale** statt einer offenen Portfreigabe – es sind
Finanzdaten.

Alle Befehle als `root` bzw. mit `sudo`.

## 1. Systempakete

```bash
apt update
apt install -y python3 python3-venv python3-pip git sqlite3 \
  libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev \
  libjpeg62-turbo libcairo2 fonts-dejavu
```

Die `libpango*`/`libcairo2`-Pakete werden von **WeasyPrint** (PDF-Export)
benötigt.

## 2. Benutzer und Code

```bash
useradd --system --home /opt/weg-abrechnung --shell /usr/sbin/nologin weg
git clone https://github.com/AtzeThon/WEG-Abrechnung.git /opt/weg-abrechnung
cd /opt/weg-abrechnung

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install ".[pdf]"
```

## 3. Konfiguration

```bash
cp .env.example .env
# Schlüssel erzeugen:
.venv/bin/python -c "import secrets; print('WEG_SECRET_KEY=' + secrets.token_urlsafe(48))" >> .env
```

`.env` anpassen – mindestens:

```ini
WEG_SECRET_KEY=<der erzeugte Wert, doppelte Zeile oben entfernen>
WEG_SECURE_COOKIES=true
WEG_DATABASE_PATH=/opt/weg-abrechnung/data/weg.db
```

```bash
mkdir -p data backups
chown -R weg:weg /opt/weg-abrechnung
```

## 4. Datenbank & Verwalter-Account

```bash
sudo -u weg .venv/bin/alembic upgrade head
sudo -u weg .venv/bin/python -m app.cli create-admin verwalter
```

Optional Demo-Datensatz (anonymisiert, zum Ausprobieren):

```bash
sudo -u weg .venv/bin/python -m scripts.seed_2026
```

## 5. systemd-Dienst

```bash
cp deploy/weg-abrechnung.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now weg-abrechnung
systemctl status weg-abrechnung
curl -s localhost:8000/gesundheit    # -> {"status":"ok"}
```

## 6. Zugriff

### Variante A: Tailscale (empfohlen)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up
tailscale serve --bg 8000          # HTTPS über den MagicDNS-Namen des Pi
```

Aufruf im Browser: `https://<pi-name>.<tailnet>.ts.net`
Caddy wird dann nicht benötigt.

### Variante B: eigene Domain über Caddy

```bash
apt install -y caddy
cp deploy/Caddyfile /etc/caddy/Caddyfile
# Domain in /etc/caddy/Caddyfile eintragen, DNS auf den Pi zeigen lassen,
# Ports 80/443 freigeben
mkdir -p /var/log/caddy && chown caddy:caddy /var/log/caddy
systemctl restart caddy
```

## 7. Tägliches Backup

```bash
cp deploy/weg-backup.service deploy/weg-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now weg-backup.timer
systemctl start weg-backup.service        # einmal manuell testen
ls -l /opt/weg-abrechnung/backups
```

Backups liegen als `weg-<zeitstempel>.db.gz` in `data/../backups` und werden
nach 30 Tagen automatisch gelöscht (`WEG_BACKUP_KEEP_DAYS` in der Unit-Umgebung
anpassbar). Zusätzlich sollte dieses Verzeichnis regelmäßig auf ein anderes
Gerät kopiert werden (z. B. `rsync` per Tailscale).

### Wiederherstellung

```bash
systemctl stop weg-abrechnung
gunzip -c backups/weg-<zeitstempel>.db.gz > data/weg.db
chown weg:weg data/weg.db
systemctl start weg-abrechnung
```

## 8. Update auf eine neue Version

```bash
cd /opt/weg-abrechnung
sudo -u weg git pull
sudo -u weg .venv/bin/pip install ".[pdf]"
systemctl restart weg-abrechnung        # führt automatisch 'alembic upgrade head' aus
```

## Fehlersuche

| Symptom | Prüfen |
|---|---|
| 502 über Caddy | `systemctl status weg-abrechnung`, `journalctl -u weg-abrechnung -e` |
| PDF-Export meldet Fehler | `libpango*` installiert? `.venv/bin/python -c "import weasyprint"` |
| Login schlägt fehl / Session weg | `WEG_SECRET_KEY` gesetzt? `WEG_SECURE_COOKIES=true` nur mit HTTPS |
| „database is locked“ | nur ein Dienst darf schreiben; WAL ist aktiv, Backups per `.backup` (nicht kopieren) |
