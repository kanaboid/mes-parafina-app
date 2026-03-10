    #!/bin/bash
# Skrypt konfigurujący Kiosk Linux Mint XFCE

echo "1. Aktualizacja i instalacja pakietów..."
sudo apt update && sudo apt install openssh-server xrdp xfce4 xfce4-goodies -y
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb -y
rm google-chrome-stable_current_amd64.deb

echo "2. Konfiguracja RDP..."
echo xfce4-session > ~/.xsession
sudo systemctl enable xrdp
sudo adduser xrdp ssl-cert

echo "3. Ubijanie wygaszaczy ekranu..."
sudo apt purge xscreensaver -y
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/blank-on-ac --create -t int -s 0
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/dpms-on-ac-off --create -t int -s 0
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/dpms-on-ac-sleep --create -t int -s 0

echo "4. Konfiguracja Autologowania..."
USER_NAME=$USER
sudo groupadd -r autologin
sudo gpasswd -a $USER_NAME autologin
sudo gpasswd -a $USER_NAME nopasswdlogin

sudo bash -c "cat > /etc/lightdm/lightdm.conf" << EOL
[Seat:*]
autologin-user=$USER_NAME
autologin-user-timeout=3
EOL

echo "5. Tworzenie skryptu Watchdoga..."
cat > ~/chrome-watchdog.sh << 'EOL'
#!/bin/bash
sleep 5
MONITOR=$(xrandr | grep " connected" | head -n 1 | awk '{print $1}')
xrandr --output "$MONITOR" --rotate right
while true; do
    timeout 4h google-chrome --kiosk --incognito --no-first-run --disable-infobars --disable-features=Translate --disable-save-password-bubble --noerrdialogs --password-store=basic 'https://mes-parafina-app-production.up.railway.app/'
    sleep 2
done
EOL
chmod +x ~/chrome-watchdog.sh

echo "6. Dodawanie Watchdoga do Autostartu XFCE..."
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/kiosk.desktop << EOL
[Desktop Entry]
Type=Application
Name=Chrome Watchdog
Exec=/home/$USER_NAME/chrome-watchdog.sh
StartupNotify=false
Terminal=false
EOL

echo "7. Ukrywanie panelu XFCE..."
sudo chmod -x /usr/bin/xfce4-panel

echo "Gotowe! System zrestartuje się za 5 sekund..."
sleep 5
sudo reboot
