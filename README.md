# Flurstücksauskunft Schleswig-Holstein

[![Lint css files](https://github.com/oklabflensburg/open-parcel-map/actions/workflows/lint-css.yml/badge.svg)](https://github.com/oklabflensburg/open-parcel-map/actions/workflows/lint-css.yml)
[![Lint html files](https://github.com/oklabflensburg/open-parcel-map/actions/workflows/lint-html.yml/badge.svg)](https://github.com/oklabflensburg/open-parcel-map/actions/workflows/lint-html.yml)
[![Lint js files](https://github.com/oklabflensburg/open-parcel-map/actions/workflows/lint-js.yml/badge.svg)](https://github.com/oklabflensburg/open-parcel-map/actions/workflows/lint-js.yml)
[![Lighthouse CI](https://github.com/oklabflensburg/open-parcel-map/actions/workflows/lighthouse.yml/badge.svg)](https://github.com/oklabflensburg/open-parcel-map/actions/workflows/lighthouse.yml)


![Screenshot der interaktiven Flurstücksauskunft](https://raw.githubusercontent.com/oklabflensburg/open-parcel-map/main/screenshot_biotopkarte.webp)

_Haftungsausschluss: Dieses Repository und die zugehörige Datenbank befinden sich derzeit in einer Beta-Version. Einige Aspekte des Codes und der Daten können noch Fehler enthalten. Bitte kontaktieren Sie uns per E-Mail oder erstellen Sie ein Issue auf GitHub, wenn Sie einen Fehler entdecken._


## Hintergrund

Diese interaktive nicht amtliche Flurstücksauskunft ohne Eigentümerangaben für Schleswig-Holstein entstand nach Gesprächen mit Bürgerinitiativen durch das OK Lab Flensburg um Verwaltungs-, Kreis-, Gemeindegrenzen, Gemarkungen und Flurstücke digital zugänglich zu machen.


## Datenquelle

Der Datensatz ALKIS Schleswig-Holstein ohne Eigentümerangaben, wird durch das Landesamt für Vermessung und Geoinformation im Open-Data Portal Schleswig-Holstein zum Download zur Verfügung gestellt.


## Aktualität

Die Aktualität der zugrundeliegenden Daten entnehmen Sie bitte der Projektseite.


## Setup

Install system dependencies and clone repository

```
sudo apt install wget
sudo apt install git git-lfs
sudo apt install python3 python3-pip python3-venv

sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget -qO- https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo tee /etc/apt/trusted.gpg.d/pgdg.asc &>/dev/null
sudo apt update
sudo apt install postgresql-16 postgis
sudo apt install gdal-bin

# install NVM (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# download and install Node.js
nvm install 20

# verifies the right Node.js version is in the environment
node -v

# verifies the right NPM version is in the environment
npm -v

git clone https://github.com/oklabflensburg/open-parcel-map.git
```

Create a dot `.env` file inside the project root. Make sure to add the following content and repace values.

```
BASE_URL=http://localhost

CONTACT_MAIL=mail@example.com
CONTACT_PHONE="+49xx"

PRIVACY_CONTACT_PERSON="Firstname Lastname"

ADDRESS_NAME="Address Name"
ADDRESS_STREET="Address Street"
ADDRESS_HOUSE_NUMBER="House Number"
ADDRESS_POSTAL_CODE="Postal Code"
ADDRESS_CITY="City"

DB_PASS=postgres
DB_HOST=localhost
DB_USER=postgres
DB_NAME=postgres
DB_PORT=5432
```


## LICENSE

[CC0-1.0](LICENSE)