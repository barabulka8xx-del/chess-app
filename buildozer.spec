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

# Жестко фиксируем версию pyjnius, чтобы не было конфликтов
requirements = python3, kivy==2.3.0, pyjnius==1.4.0

orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.accept_sdk_license = True
android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 21

android.release_artifact = apk

# Разрешение на интернет и вибрацию
android.permissions = INTERNET, VIBRATE
