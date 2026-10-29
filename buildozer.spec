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

# ЖЕСТКО ФИКСИРУЕМ PYTHON 3.10!
requirements = python3==3.10.8, kivy==2.3.0

orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.accept_sdk_license = True
android.permissions = INTERNET

# Отключаем параллельность для Gradle
android.gradle_parallel = False
android.gradle_daemon = False
