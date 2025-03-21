# Traffic Filters 👀

Display filtered video streams from Seattle Department of Transit (SDOT) cameras.
[link](https://web.seattle.gov/Travelers/)


## Setup

- `git clone git@github.com:camoverride/traffic_filters.git`
- `cd traffic_filters`
- `python3 -m venv .venv`
- `source .venv/bin/activate`
- `pip install -r requirements.txt`
- `sudo apt-get install unclutter`

Add the dimensions of your monitor to `config.yaml` and optionally
select a new traffic camera.


## Run

- `mkdir -p ~/.config/systemd/user`
- `cat display.service > ~/.config/systemd/user/display.service`
- `systemctl --user daemon-reload`
- `systemctl --user enable display.service`
- `systemctl --user start display.service`
- `sudo loginctl enable-linger $(whoami)`
