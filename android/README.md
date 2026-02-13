Android - meshtastic

wget https://github.com/projectqai/hydris/releases/download/v0.0.18/app-release.apk

adb install -r hydris.apk


--

Download the APK and install on your device.

Sideloading with ADB:

    Enable Developer Options on your Android device:
        Go to Settings → About Phone
        Tap "Build Number" 7 times

    Enable USB Debugging:
        Go to Settings → Developer Options
        Enable "USB Debugging"

    Connect your device and install:

    adb install -r hydris.apk

