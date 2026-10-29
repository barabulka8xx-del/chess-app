[app]
title = Chess By Lord
package.name = chessbylord
package.domain = ru.lord
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav,ttf,ogg,mp3
version = 1.4.2
android.numeric_version = 142

icon.filename = icon.png
presplash.filename = icon.png

# Без pyjnius, только база
requirements = python3, kivy==2.3.0

orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.accept_sdk_license = True
android.api = 31
android.minapi = 24
android.ndk = 23b
android.ndk_api = 21

android.release_artifact = apk
android.permissions = INTERNET, VIBRATE
