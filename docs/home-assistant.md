# Connecting your computer to Home Assistant

From nothing to a dashboard card and voice commands.

## What you get

- A device in Home Assistant with every button and sensor — **without a single
  line of YAML** for them.
- A shutdown countdown that ticks every second and reads the same wherever it
  was started from.
- Turning the computer on over Wake-on-LAN.
- Voice commands for on and off.
- Home Assistant learns the computer died instantly rather than by timeout.

## What you need

| | |
|---|---|
| Computer | Windows 10 or 11, Python 3.10+ (or the prebuilt exe) |
| Home Assistant | any flavour |
| MQTT broker | usually the Mosquitto broker add-on |
| Network | the computer and Home Assistant can see each other |

MQTT is not mandatory, but it makes everything simpler: without it every
entity has to be declared by hand. If you have no broker yet, it takes a
minute to install and the rest of the house will use it too.

---

## Step 1. Install the remote on the computer

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

Or, from a build, `pc-remote.exe --install`.

It installs the dependencies, registers autostart, starts the service and
checks that it answers. The address it prints is the one you need below.

Open `http://<address>:5000/admin` and **change the password right away**
(Access → Password). The default is `changeme`.

Check that everything works: `http://<address>:5000` should show the remote,
and the Lock button should lock the screen.

---

## Step 2. The MQTT broker

Skip this if you already have one.

1. **Settings → Add-ons → Store** → install **Mosquitto broker**, start it and
   enable "Start on boot".
2. **Settings → People** → add a user, for example `mqtt-devices`, with normal
   rights. This is the account devices use — separate from yours, so its
   password can change independently.
3. **Settings → Devices & services** → Mosquitto will offer to set up the MQTT
   integration itself. Accept.

From outside, the broker address is the address of Home Assistant itself, port
`1883`. The internal name `core-mosquitto` only works inside Home Assistant and
will not do for the computer.

---

## Step 3. Point the remote at the broker

In the remote's settings: **Integrations → MQTT bridge** → turn the switch on
and fill in:

| Field | Value |
|---|---|
| Broker address | the Home Assistant address, e.g. `192.168.1.10` |
| Port | `1883` |
| Username / Password | the account from step 2 |
| Device name | what to call the computer in Home Assistant |

Save. The status line should turn green: "connected · <device>". If it does
not, press Reconnect and look at the Log tab.

**A ready device appears in Home Assistant within a couple of seconds:**
Settings → Devices & services → MQTT.

What arrives:

- **Buttons** — one per enabled action. Disable an action in the remote's
  settings and its button disappears here too.
- `sensor.<name>_shutdown_in` — seconds until shutdown, ticking on its own.
- `sensor.<name>_status` — a ready sentence: "Online" or "Shutdown in 12 s".
- `sensor.<name>_uptime` — how long the remote has been running.
- `binary_sensor.<name>_remote` — whether the remote answers.

The exact entity ids are on the device page: they are built from the name you
chose.

---

## Step 4. Turning the computer on

The remote lives on the computer and cannot wake it — Wake-on-LAN does that.

**On the computer:**

1. Enable *Wake on LAN* / *Power On by PCI-E* in the BIOS/UEFI.
2. Device Manager → network adapter → Properties → Power Management: allow it
   to wake the computer, and "Only magic packet".
3. **Turn fast startup off** — otherwise Windows does not really shut down but
   enters a hybrid state a magic packet cannot wake:
   ```powershell
   powercfg /hibernate off
   ```
   (or Control Panel → Power Options → Choose what the power buttons do →
   uncheck "Turn on fast startup")
4. Find the MAC address: `getmac /v` — take the adapter the computer is
   actually connected through.

**In Home Assistant** — `configuration.yaml` or a package of your own:

```yaml
switch:
  - platform: wake_on_lan
    name: "Computer"
    mac: "AA:BB:CC:DD:EE:FF"
    host: 192.168.1.50          # so the state can be determined by ping
    turn_off:
      # Shutdown travels to the remote through the same broker
      action: mqtt.publish
      data:
        topic: "pc-remote/<node>/cmd"
        payload: "shutdown"
```

`<node>` is what the remote shows under Integrations, "topics:
pc-remote/…". Usually the computer name in lowercase Latin.

The result is a single switch: on via Wake-on-LAN, off through the remote.
The state comes from a ping, so "off" appears a few seconds after the real
shutdown rather than instantly.

---

## Step 5. Voice commands

Voice assistants understand a **switch** (on/off), not individual buttons.
So expose `switch.computer` from step 4 through whichever integration you use.

"Turn on the computer" then sends a magic packet, and "turn off the computer"
starts the countdown — with enough time to change your mind.

---

## Step 6. A dashboard card

The quickest option is the whole device: Settings → Devices & services → MQTT →
your computer → "Add to dashboard".

By hand, more carefully:

```yaml
type: vertical-stack
cards:
  - type: heading
    heading: Computer
    icon: mdi:desktop-tower-monitor

  - type: tile
    entity: switch.computer
    state_content: [state, last-changed]

  # The countdown only shows while it runs
  - type: conditional
    conditions:
      - condition: numeric_state
        entity: sensor.computer_shutdown_in
        above: 0
    card:
      type: entities
      entities:
        - entity: sensor.computer_shutdown_in
        - entity: button.computer_cancel

  # Actions only while the computer is online
  - type: conditional
    conditions:
      - condition: state
        entity: switch.computer
        state: "on"
    card:
      type: horizontal-stack
      cards:
        - type: button
          entity: button.computer_sleep
        - type: button
          entity: button.computer_lock
        - type: button
          entity: button.computer_mute
```

The point of the conditional blocks: do not show buttons that would do nothing
right now, and do not make anyone hunt for cancel once a countdown has started.

---

## Optional: a second channel over HTTP

MQTT is the only dependency on the broker. If it goes down, the buttons in
Home Assistant become unavailable. If you want commands to arrive regardless,
add a direct HTTP call.

1. In the remote's settings: **Integrations → Tokens** → issue one, for example
   "Home Assistant". The value is shown **once**.
2. In `secrets.yaml`:
   ```yaml
   pc_remote_token_header: "Bearer <token>"
   ```
3. In the configuration:
   ```yaml
   rest_command:
     pc_control:
       url: "http://192.168.1.50:5000/api"
       method: POST
       timeout: 15
       headers:
         Content-Type: "application/json"
         Authorization: !secret pc_remote_token_header
       payload: '{"action": "{{ action }}", "delay": {{ delay | default(30) | int(30) }}}'
   ```
4. Call it with `action: rest_command.pc_control` and `data: {action: shutdown}`.

**Why a token and not the password.** The remote's password is for a human and
gets changed when it leaks or gets old. If Home Assistant uses the same one,
every change silently breaks every automation. A token is issued separately and
revoked on its own.

A good compromise: take state from MQTT, where it arrives instantly by itself,
and send commands over HTTP, which does not depend on the broker.

---

## Checking it works

| What | Where |
|---|---|
| The remote is alive | `http://<address>:5000` opens |
| The broker is connected | the status line in the settings is green |
| The device was created | Settings → Devices & services → MQTT |
| Commands arrive | press a button and open the Log tab in the settings |
| Waking works | shut the computer down and try the switch |

Every command appears in the log with the sender's address:

```
14:51:12  192.168.1.10 -> shutdown (delay=30): Shutdown in 30 s. You can still cancel.
```

---

## If something is wrong

| Symptom | Cause |
|---|---|
| No device in Home Assistant | the broker is not connected — see the Log tab |
| It appeared but everything is unavailable | the remote is not running, or Home Assistant's network is not on the allow-list |
| Buttons press, nothing happens | the action is disabled in the remote's settings |
| The computer does not wake | fast startup is still on — the most common cause |
| It does not wake after a full power cut | the BIOS gives the network card no standby power |
| The switch says "on" for a computer that is off | the state comes from a ping, give it a few seconds |
| Everything broke after a password change | the integration used the password — move it to a token |
| Everything disappeared after a reboot | autostart: the Overview tab shows its state |

The remote's log is the only place that shows what it did and where it failed:
Settings → Log, or `data/server.log` on the computer itself.
