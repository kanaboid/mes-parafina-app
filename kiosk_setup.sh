#!/bin/bash
# Kompletny skrypt instalacyjno-konfiguracyjny: Kiosk Linux Mint XFCE + Panel Webowy

# Skrypt uruchamiaj jako zalogowany użytkownik kiosku (nie jako bezpośredni 'root'), 
# użyje on sudo w miejscach, w których to potrzebne.
USER_NAME=$USER

echo "1. Aktualizacja i instalacja pakietów..."
sudo apt update && sudo apt install openssh-server xrdp xfce4 xfce4-goodies python3-flask unclutter autorandr -y
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb -y
rm google-chrome-stable_current_amd64.deb

echo "2. Konfiguracja RDP..."
echo xfce4-session > ~/.xsession
sudo systemctl enable xrdp
sudo adduser xrdp ssl-cert

echo "3. Konfiguracja zapory sieciowej (UFW)..."
sudo ufw allow 22/tcp
sudo ufw allow 3389/tcp
sudo ufw allow 5000/tcp
sudo ufw --force enable

echo "4. Ubijanie wygaszaczy ekranu i powiadomień..."
sudo apt purge xscreensaver mintupdate mintwelcome xfce4-notifyd -y
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/blank-on-ac --create -t int -s 0
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/dpms-on-ac-off --create -t int -s 0
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/dpms-on-ac-sleep --create -t int -s 0

echo "5. Konfiguracja Autologowania..."
sudo groupadd -r autologin
sudo gpasswd -a $USER_NAME autologin
sudo gpasswd -a $USER_NAME nopasswdlogin

sudo bash -c "cat > /etc/lightdm/lightdm.conf" << EOL
[Seat:*]
autologin-user=$USER_NAME
autologin-user-timeout=3
EOL

echo "6. Tworzenie podstawowego pliku konfiguracyjnego..."
cat > /home/$USER_NAME/kiosk_config.env << EOL
ROTATION=normal
URL=https://mes-parafina-app-production.up.railway.app/
EOL

echo "7. Tworzenie skryptu Watchdoga..."
cat > /home/$USER_NAME/chrome-watchdog.sh << 'EOL'
#!/bin/bash
CONFIG_FILE="/home/$USER/kiosk_config.env"

sleep 5
source "$CONFIG_FILE"
MONITOR=$(xrandr | grep " connected" | head -n 1 | awk '{print $1}')

# Uruchomienie ukrywania kursora (w tle) ZANIM wejdziemy w nieskończoną pętlę
unclutter -idle 0.1 -root &

# Ustawienie rotacji na podstawie pliku konfiguracyjnego i wymuszenie zapisu profilu
xrandr --output "$MONITOR" --rotate $ROTATION
autorandr --save ekran-rotacja --force

while true; do
    source "$CONFIG_FILE"
    timeout 4h google-chrome --kiosk --incognito --no-first-run --disable-infobars --disable-features=Translate --disable-save-password-bubble --noerrdialogs --password-store=basic "$URL"
    sleep 2
done
EOL
chmod +x /home/$USER_NAME/chrome-watchdog.sh

echo "8. Dodawanie Watchdoga do Autostartu XFCE..."
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/kiosk.desktop << EOL[Desktop Entry]
Type=Application
Name=Chrome Watchdog
Exec=/home/$USER_NAME/chrome-watchdog.sh
StartupNotify=false
Terminal=false
EOL

echo "9. Tworzenie Panelu Webowego (z Auto-Odświeżaniem)..."
cat > /home/$USER_NAME/kiosk_admin.py << 'EOL'
from flask import Flask, request, render_template_string, redirect, url_for
import os
import threading
import time

app = Flask(__name__)
CONFIG_FILE = os.path.expanduser("~/kiosk_config.env")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel Administracyjny Kiosku</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f9; color: #333; padding: 40px; }
        .container { max-width: 500px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        h2 { text-align: center; color: #0056b3; }
        label { font-weight: bold; display: block; margin-top: 15px; margin-bottom: 5px; }
        input[type="text"], select { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        button { margin-top: 25px; width: 100%; padding: 12px; background-color: #0056b3; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold; }
        button:hover { background-color: #004494; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Ustawienia Terminala</h2>
        <form method="POST">
            <label>Adres URL Strony:</label>
            <input type="text" name="url" value="{{ url }}" required>
            
            <label>Orientacja (Rotacja) Ekranu:</label>
            <select name="rotation">
                <option value="normal" {% if rot == 'normal' %}selected{% endif %}>Poziomo (Normalnie)</option>
                <option value="right" {% if rot == 'right' %}selected{% endif %}>Pionowo (Obrót w prawo)</option>
                <option value="left" {% if rot == 'left' %}selected{% endif %}>Pionowo (Obrót w lewo)</option>
                <option value="inverted" {% if rot == 'inverted' %}selected{% endif %}>Odwrócony (Do góry nogami)</option>
            </select>
            
            <button type="submit">Zapisz ustawienia i zrestartuj</button>
        </form>
    </div>
</body>
</html>
"""

SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="30; url=/">
    <title>Restartowanie...</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f9; color: #333; padding: 50px; text-align: center; }
        .box { max-width: 500px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        h2 { color: #28a745; }
        p { font-size: 16px; color: #555; }
        .loader { border: 4px solid #f3f3f3; border-top: 4px solid #0056b3; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 20px auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="box">
        <h2>Zapisano pomyślnie!</h2>
        <p>Trwa restartowanie terminala...</p>
        <div class="loader"></div>
        <p>Strona odświeży się automatycznie za około 30 sekund.</p>
    </div>
</body>
</html>
"""

def read_config():
    config = {'URL': '', 'ROTATION': 'normal'}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                if '=' in line:
                    key, val = line.strip().split('=', 1)
                    config[key] = val
    return config

def delayed_reboot():
    time.sleep(2)
    os.system("sudo /usr/sbin/reboot")

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        new_url = request.form['url']
        new_rot = request.form['rotation']
        
        with open(CONFIG_FILE, 'w') as f:
            f.write(f"ROTATION={new_rot}\n")
            f.write(f"URL={new_url}\n")
            
        return redirect(url_for('success'))

    config = read_config()
    return render_template_string(HTML_TEMPLATE, url=config.get('URL', ''), rot=config.get('ROTATION', 'normal'))

@app.route('/success')
def success():
    threading.Thread(target=delayed_reboot).start()
    return render_template_string(SUCCESS_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOL

echo "10. Nadawanie uprawnień do restartowania systemu..."
echo "$USER_NAME ALL=(ALL) NOPASSWD: /usr/sbin/reboot" | sudo tee /etc/sudoers.d/kiosk_reboot
sudo chmod 0440 /etc/sudoers.d/kiosk_reboot

echo "11. Tworzenie usługi systemowej (Systemd) dla Panelu Webowego..."
sudo bash -c "cat > /etc/systemd/system/kiosk-admin.service" << EOL
[Unit]
Description=Kiosk Admin Web Panel
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=/home/$USER_NAME
ExecStart=/usr/bin/python3 /home/$USER_NAME/kiosk_admin.py
Restart=always

[Install]
WantedBy=multi-user.target
EOL

echo "12. Ukrywanie panelu XFCE i opcji ekranu..."
sudo chmod -x /usr/bin/xfce4-panel
sudo chmod -x /usr/bin/xfce4-display-settings

echo "13. Rejestrowanie i uruchamianie usług..."
sudo systemctl daemon-reload
sudo systemctl enable kiosk-admin.service
sudo systemctl start kiosk-admin.service
sudo systemctl enable --now autorandr.service

echo "=========================================================="
echo "Gotowe! Kompletna instalacja zakończona sukcesem."
echo "Po restarcie zarządzanie Kioskiem będzie dostępne pod adresem:"
echo "http://$(hostname -I | awk '{print $1}'):5000"
echo "System zrestartuje się za 5 sekund..."
echo "=========================================================="
sleep 5
sudo reboot