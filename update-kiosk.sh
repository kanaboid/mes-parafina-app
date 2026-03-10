#!/bin/bash
# Skrypt wprowadzający Panel Webowy (Opcja 1) dla Kiosku HP t630

USER_NAME=$USER
echo "1. Instalacja pakietu Flask..."
sudo apt update
sudo apt install python3-flask -y

echo "2. Konfiguracja zapory sieciowej (UFW)..."
# Zabezpieczamy się przed odcięciem od SSH i RDP
sudo ufw allow 22/tcp
sudo ufw allow 3389/tcp
# Otwieramy port 5000 dla naszego Panelu Webowego
sudo ufw allow 5000/tcp
# Włączamy zaporę (jeśli była wyłączona) - bez przerywania obecnych połączeń
sudo ufw --force enable

echo "3. Tworzenie podstawowego pliku konfiguracyjnego..."
cat > /home/$USER_NAME/kiosk_config.env << EOL
ROTATION=normal
URL=https://mes-parafina-app-production.up.railway.app/
EOL

echo "4. Modyfikacja skryptu Watchdoga..."
# Używamy 'EOL' (w apostrofach), aby zmienne bashowe nie wykonały się podczas tworzenia pliku
cat > /home/$USER_NAME/chrome-watchdog.sh << 'EOL'
#!/bin/bash
CONFIG_FILE="/home/$USER/kiosk_config.env"

sleep 5
source "$CONFIG_FILE"
MONITOR=$(xrandr | grep " connected" | head -n 1 | awk '{print $1}')

# Ustawienie rotacji
xrandr --output "$MONITOR" --rotate $ROTATION

while true; do
    # Wczytujemy plik w pętli (gdybyśmy zmienili dane ręcznie w tle)
    source "$CONFIG_FILE"
    
    timeout 4h google-chrome --kiosk --incognito --no-first-run --disable-infobars --disable-features=Translate --disable-save-password-bubble --noerrdialogs --password-store=basic "$URL"
    
    sleep 2
done
EOL
chmod +x /home/$USER_NAME/chrome-watchdog.sh

echo "5. Tworzenie Panelu Webowego w Pythonie..."
cat > /home/$USER_NAME/kiosk_admin.py << 'EOL'
from flask import Flask, request, render_template_string
import os

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
        .success { text-align: center; color: green; font-size: 18px; margin-top: 20px; }
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

def read_config():
    config = {'URL': '', 'ROTATION': 'normal'}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                if '=' in line:
                    key, val = line.strip().split('=', 1)
                    config[key] = val
    return config

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        new_url = request.form['url']
        new_rot = request.form['rotation']
        
        with open(CONFIG_FILE, 'w') as f:
            f.write(f"ROTATION={new_rot}\n")
            f.write(f"URL={new_url}\n")
            
        # Zezwolenie na restart z poziomu skryptu
        os.system("sudo /usr/sbin/reboot")
        return "<h2 style='text-align:center; color:green; font-family:sans-serif;'>Zapisano pomyślnie! Trwa restart terminala... <br>Odśwież stronę za 30 sekund.</h2>"

    config = read_config()
    return render_template_string(HTML_TEMPLATE, url=config.get('URL', ''), rot=config.get('ROTATION', 'normal'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOL

echo "6. Nadawanie uprawnień do restartowania systemu z poziomu przeglądarki..."
echo "$USER_NAME ALL=(ALL) NOPASSWD: /usr/sbin/reboot" | sudo tee /etc/sudoers.d/kiosk_reboot
sudo chmod 0440 /etc/sudoers.d/kiosk_reboot

echo "7. Tworzenie usługi systemowej (Systemd) dla Panelu Webowego..."
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

echo "8. Uruchamianie usługi..."
sudo systemctl daemon-reload
sudo systemctl enable kiosk-admin.service
sudo systemctl start kiosk-admin.service

echo "=========================================================="
echo "Gotowe! Narzędzie administracyjne zostało zainstalowane."
echo "Z panelu na swoim komputerze wpisz w przeglądarkę:"
echo "http://$(hostname -I | awk '{print $1}'):5000"
echo "System zostanie teraz zrestartowany, aby zastosować zmiany."
echo "=========================================================="
sleep 5
sudo reboot
