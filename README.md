# Open-ORBA

An experimental Linux companion app for **Artiphon ORBA 3 only**. The desktop app currently appears as **Orba Studio** (preview 0.2).

**ORBA 3 only:** This project targets ORBA 3. ORBA 1, ORBA 2, Chorda, and other Artiphon instruments are unsupported. A shared USB identifier or similar protocol does not establish compatibility with another model.

**Disclaimer — Testing Purposes Only:** This software is provided for testing and experimental purposes only. There is no guarantee that it will work out of the box with your specific hardware revision, firmware version, Linux distribution, or audio pipeline. However, it serves as a solid foundation and reference implementation for your own fork and customization.

This is an independent community project and is not affiliated with or endorsed by Artiphon.

## Features

- USB MIDI connection with automatic device discovery, battery, tempo, part selection, notes, and gestures.
- Hardware part order and colors: 1 Drum turquoise, 2 Bass blue, 3 Chord orange, 4 Lead magenta.
- MIDI recording and standard `.mid` export.
- Stereo WAV recording from the ORBA 3 USB audio input at 48 kHz / 24-bit.
- A local sound library with search, part filters, Artiphon bundle/preset import, sample dependency inspection, individual sample previews, and ZIP export with dependencies.
- Device storage connection, complete file backups, and verified preset/sample copies that refuse to replace different existing files.

## Current limitations

**Activating transferred presets remains unverified and is unavailable in the interface.** Device name/filename queries returned empty strings during testing. Copying a preset to storage does not select it.

Song files can be copied and backed up; loading a song into the current device session is not implemented. Firmware updates, Bluetooth, local synthesis, and key/scale editing are also not implemented.

WAV export records live USB audio. Play the instrument or its loop while recording, then press **Stop & save WAV**. Offline rendering of MIDI and direct export of stored loops are not implemented. Sample previews play individual WAV files, rather than reproducing a complete preset.

## Install and run

Requires Python 3 with Tk, `ffmpeg`/`ffplay`, `pactl` with a working PulseAudio or PipeWire PulseAudio compatibility server, `pkexec` with a desktop authentication agent, and `mount`/`findmnt` from util-linux.

For Arch Linux:

```bash
sudo pacman -S python tk ffmpeg libpulse polkit util-linux
```

For Debian / Ubuntu:

```bash
sudo apt install python3 python3-tk ffmpeg pulseaudio-utils pkexec util-linux
```

Keep your existing desktop audio server. Under PipeWire, enable its PulseAudio compatibility service so `pactl` and FFmpeg's PulseAudio input can access the ORBA 3 audio source.

```bash
git clone https://github.com/hsantos92/Open-ORBA.git
cd Open-ORBA
./launch.sh
```

The app requires user access to the ALSA MIDI device. Run the app as your normal desktop user. Storage operations request desktop authentication through narrowly scoped helpers. Avoid running another companion app concurrently.

## Bring your own sound library

Sound assets, vendor installers, device backups, and recordings are **not included**. A fresh clone starts with an empty library. Open **Sound library → Import…** to add your own `.artibundle`, `.artipreset`, `.artisong`, or ZIP files. Presets that reference samples need those sample files available in the imported library.

Use **Export sound bundle…** to create a portable ZIP containing a sound and its available dependencies. These ZIPs use Open-ORBA's own format, not the proprietary Artiphon `.artibundle` format. Ensure you have permission before sharing sound assets.

## Storage workflow

1. Stop and save recordings, then choose **Connect storage**. Performance controls pause during storage access.
2. Choose **Back up Orba…** before copying sounds. The backup verifies file hashes and includes a manifest.
3. Select a sound with all its referenced files available, then choose **Copy to Orba storage**. Existing identical files are verified and reused; different files are not overwritten.
4. Choose **Eject storage**, then unplug USB and restart the instrument before reconnecting.

During testing, storage mode persisted through an ordinary power-button press. If the instrument remains unresponsive after ejecting and unplugging, hold **Volume Down (−) and Power together for 15 seconds**, release both, then power on and reconnect. This is the forced-power-off procedure in [Artiphon's Orba family manual](https://www.bhphotovideo.com/lit_files/1203820.pdf). Volume Up with Power can enter firmware update mode.

The storage helper uses USB identity and volume markers; the storage USB identity is shared by some Artiphon hardware. Physically verify that the connected instrument is ORBA 3 and connect only one instrument while using storage tools.

## Validation and development

```bash
python3 -m unittest -v
```

The ten automated tests cover packet framing, MIDI event handling/export, bundle dependencies, unsafe archive paths, and verified non-overwriting copies. They do not require a connected instrument or change device storage.

Development testing on one ORBA 3 verified normal settings replies, a custom preset file copy with its 16 samples already present and hash-verified, and audible USB WAV recording. This is not a compatibility guarantee for other firmware or Linux configurations. Experimental device scripts and private development artifacts are excluded from the repository.

## License and attribution

The original code in this repository is licensed under the [MIT License](LICENSE). Artiphon software, sounds, firmware, trademarks, and user-provided content are not covered by that license.

Protocol framing uses an independent implementation informed by the [community ORBA protocol specification](https://github.com/holofermes/orba-protocol) (specification CC BY 4.0), plus inspection of user-supplied desktop software. The community specification primarily targets ORBA 2; this project's supported target remains ORBA 3. See [NOTICE](NOTICE) for attribution.
